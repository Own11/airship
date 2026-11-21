"""Integration coverage for safe regeneration and public benchmark logs."""
import importlib.util
import json
import os
import subprocess
import sys
import shutil
from pathlib import Path

import pytest

from fintech_rl.cli import commands


def test_benchmark_configuration_covers_zero_to_twelve_issues():
    configs = commands.TRAIN_CONFIGS + commands.DEV_CONFIGS
    costs = [sum(2 if kind in {"X1", "X2"} else 1 for kind in kinds)
             for _, _, kinds in configs]
    assert len(configs) == 20
    assert len({episode_id for episode_id, _, _ in configs}) == 20
    assert set(costs) == set(range(13))
    assert costs.count(0) == 5
    assert costs.count(12) == 1
    assert {kind for _, _, kinds in configs for kind in kinds} == {
        "E1", "E2", "E3", "E4", "X1", "X2",
    }


def test_batch_generation_failure_preserves_all_published_files(tmp_path, monkeypatch):
    published = tmp_path / "train" / "train_ep_01"
    published.mkdir(parents=True)
    (published / "ledger.csv").write_bytes(b"previous ledger")
    (published / "team-result.txt").write_bytes(b"valuable team result")
    monkeypatch.setattr(commands, "get_episodes_dir", lambda: tmp_path)
    calls = []

    def reject_candidate(episode_id, seed, kinds, stage_dir):
        calls.append(episode_id)
        if len(calls) == 2:
            raise ValueError("invalid candidate")
        stage_dir.mkdir(parents=True)
        for filename in commands.EPISODE_FILENAMES:
            (stage_dir / filename).write_bytes(b"candidate")
        from types import SimpleNamespace
        return SimpleNamespace(ledger=[1] * 200), SimpleNamespace(issues=[])

    monkeypatch.setattr(commands, "stage_episode", reject_candidate)
    with pytest.raises(ValueError, match="invalid candidate"):
        commands.cmd_generate()
    assert (published / "ledger.csv").read_bytes() == b"previous ledger"
    assert (published / "team-result.txt").read_bytes() == b"valuable team result"
    assert not list(tmp_path.glob(".staging-*"))


def test_publish_replaces_only_generated_artifacts(tmp_path):
    stage, target = tmp_path / "stage", tmp_path / "published"
    stage.mkdir()
    target.mkdir()
    (target / "team-result.txt").write_bytes(b"keep")
    for filename in commands.EPISODE_FILENAMES:
        (stage / filename).write_bytes(b"new")
        (target / filename).write_bytes(b"old")
    commands.publish_staged_episodes([(stage, target)])
    assert (target / "team-result.txt").read_bytes() == b"keep"
    assert all((target / name).read_bytes() == b"new" for name in commands.EPISODE_FILENAMES)


def test_publish_io_failure_rolls_back_replaced_files(tmp_path, monkeypatch):
    stage, target = tmp_path / "stage", tmp_path / "published"
    stage.mkdir()
    target.mkdir()
    for filename in commands.EPISODE_FILENAMES:
        (stage / filename).write_bytes(b"new")
        (target / filename).write_bytes(b"old")
    actual_replace = commands.os.replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated disk error")
        return actual_replace(source, destination)

    monkeypatch.setattr(commands.os, "replace", fail_second_replace)
    with pytest.raises(OSError, match="simulated disk error"):
        commands.publish_staged_episodes([(stage, target)])
    assert all((target / name).read_bytes() == b"old" for name in commands.EPISODE_FILENAMES)


def test_public_trajectories_exclude_oracle_and_evaluator_data(tmp_path, monkeypatch):
    source = commands.ROOT_DIR / "episodes" / "train" / "train_ep_03"
    target = tmp_path / "episodes" / "train" / "train_ep_03"
    target.mkdir(parents=True)
    for filename in commands.EPISODE_FILENAMES:
        shutil.copy2(source / filename, target / filename)
    monkeypatch.setattr(commands, "get_episodes_dir", lambda: tmp_path / "episodes")
    monkeypatch.setattr(commands, "format_score", lambda value, **kwargs: f"{value:.3f}")
    tables = []
    monkeypatch.setattr(commands, "print_table", lambda headers, rows, **kwargs: tables.append(rows))
    trajectories = tmp_path / "public.jsonl"
    assert commands.cmd_benchmark("train", str(trajectories)) == 0
    records = [json.loads(line) for line in trajectories.read_text(encoding="utf-8").splitlines()]
    assert {r["policy"] for r in records} == {
        "simple_reconciler", "random_explorer", "mark_all",
    }
    assert all(r["reward"] == 0.0 for r in records)
    text = trajectories.read_text(encoding="utf-8")
    for private_value in ("truth.json", "provenance.json", "ISSUE-", "evaluator_", str(source)):
        assert private_value not in text
    assert all("eval_metrics" not in r for r in records)
    # The harness still reports the exact evaluator's perfect Oracle score.
    assert tables[0][0][1:4] == ["1.000", "1.000", "1.000"]
    assert tables[1][0][1] == "0.998"
    assert tables[1][-1][1] == "-1.000"


def test_script_helper_invalid_generation_keeps_original_output(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "airship_make_episodes_test", commands.ROOT_DIR / "scripts" / "make_episodes.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    target = tmp_path / "published"
    target.mkdir()
    (target / "ledger.csv").write_bytes(b"previous data")
    (target / "team-result.txt").write_bytes(b"keep")
    with pytest.raises(ValueError):
        module.generate_episode("invalid", 42, target, ["unknown-error"])
    assert (target / "ledger.csv").read_bytes() == b"previous data"
    assert (target / "team-result.txt").read_bytes() == b"keep"
    assert not list(tmp_path.glob(".staging-*"))


def test_failed_benchmark_keeps_previous_results(tmp_path, monkeypatch):
    from fintech_rl.policies.random_explorer import RandomExplorerPolicy
    source = commands.ROOT_DIR / "episodes" / "train" / "train_ep_03"
    target = tmp_path / "episodes" / "train" / "train_ep_03"
    target.mkdir(parents=True)
    for filename in commands.EPISODE_FILENAMES:
        shutil.copy2(source / filename, target / filename)
    monkeypatch.setattr(commands, "get_episodes_dir", lambda: tmp_path / "episodes")
    trajectories = tmp_path / "public.jsonl"
    trajectories.write_bytes(b"previous verified benchmark")

    def fail_policy(self, observation):
        raise RuntimeError("simulated policy failure")

    monkeypatch.setattr(RandomExplorerPolicy, "act", fail_policy)
    with pytest.raises(RuntimeError, match="simulated policy failure"):
        commands.cmd_benchmark("train", str(trajectories))
    assert trajectories.read_bytes() == b"previous verified benchmark"
    assert not list(tmp_path.glob(".trajectory-*"))


@pytest.mark.parametrize("arguments, expected", [
    (["--help"], "AIRSHIP COMMAND LINE INTERFACE"),
    (["inspect", "train_ep_03", "--table", "ledger", "--limit", "1"], "LEDGER RECORDS"),
])
def test_cli_redirected_legacy_encoding_outputs_utf8(arguments, expected):
    environment = dict(os.environ, PYTHONIOENCODING="cp1251", PYTHONUTF8="0")
    completed = subprocess.run(
        [sys.executable, "-m", "airship", *arguments],
        cwd=commands.ROOT_DIR, env=environment, capture_output=True, timeout=30,
    )
    error = completed.stderr.decode("utf-8")
    assert completed.returncode == 0, error
    output = completed.stdout.decode("utf-8")
    assert expected in output
    assert "UnicodeEncodeError" not in error


def test_output_configuration_preserves_utf8_and_capture_streams(monkeypatch):
    import io
    from fintech_rl.cli.main import _configure_output_streams

    class ExistingUTF8Stream:
        encoding = "UTF-8"

        def reconfigure(self, **kwargs):
            raise AssertionError("Existing UTF-8 configuration must stay unchanged")

    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", ExistingUTF8Stream())
    monkeypatch.setattr(sys, "stderr", captured)
    _configure_output_streams()
    assert not captured.closed


def test_cli_reconfigures_legacy_stderr_to_utf8():
    environment = dict(os.environ, PYTHONIOENCODING="cp1251", PYTHONUTF8="0")
    completed = subprocess.run(
        [sys.executable, "-c",
         "from fintech_rl.cli.main import main; import sys; main(['--help']); "
         "print('\\u25b6 \\u20ac', file=sys.stderr)"],
        cwd=commands.ROOT_DIR, env=environment, capture_output=True, timeout=30,
    )
    assert completed.returncode == 0
    assert completed.stderr.decode("utf-8").splitlines() == ["\u25b6 \u20ac"]
