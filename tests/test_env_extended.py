"""Integration coverage for generated resets, public APIs, and security boundaries."""

import csv
import json
from decimal import Decimal, localcontext

import pytest

from fintech_rl.env.actions import ActionHandler, safe_eval_expression
from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.generator.episode import generate_episode
from fintech_rl.identifiers import fx_record_id


@pytest.fixture
def disk_episode(tmp_path):
    company, truth, provenance = generate_episode(73, episode_id="disk_episode", error_types=["E1"])
    directory = tmp_path / "disk_episode"
    render_episode_files(company, truth, provenance, directory)
    return directory


def public_snapshot(env):
    handler = env.action_handler
    return (handler.ledger, handler.invoices, handler.payments, handler.fx_rates)


def test_generated_seed_and_action_sequence_reproducibility():
    left, right = FinancialAuditEnv(), FinancialAuditEnv()
    assert left.reset(seed=42) == right.reset(seed=42)
    assert public_snapshot(left) == public_snapshot(right)
    actions = [
        {"type": "list_records", "table": "ledger", "limit": 50},
        {"type": "list_records", "table": "invoices", "limit": 50},
        {"type": "calculator", "expression": "123.456 * 789"},
        {"type": "get_record", "table": "fx", "id": "2025-01-01:EUR:USD"},
        {"type": "submit", "findings": []},
    ]
    for action in actions:
        assert left.step(action) == right.step(action)


def test_distinct_seeds_and_repeated_reset_clear_entire_episode():
    env = FinancialAuditEnv()
    initial, _ = env.reset(seed=42)
    original = json.dumps(public_snapshot(env), sort_keys=True)
    env.step({"type": "submit", "findings": []})
    env.reset(seed=43)
    assert json.dumps(public_snapshot(env), sort_keys=True) != original
    env.action_handler.ledger.clear()
    env.evaluator_metrics = {"stale_private_state": True}
    observation, _ = env.reset(seed=42)
    assert observation == initial
    assert json.dumps(public_snapshot(env), sort_keys=True) == original
    assert env.current_step == 0 and not env.is_terminated and not env.is_truncated
    assert env.evaluator_metrics == {} and env.evaluator_reward == 0.0


def test_generation_does_not_open_or_create_files(monkeypatch):
    def reject_io(*args, **kwargs):
        raise AssertionError("generated reset must not access files")
    monkeypatch.setattr("builtins.open", reject_io)
    env = FinancialAuditEnv()
    observation, _ = env.reset(seed=42)
    assert observation["manifest_summary"]["n_records"] >= 200
    assert env.episode_dir is None


def test_directory_priority_generation_override_and_directory_fallback(disk_episode):
    env = FinancialAuditEnv(episode_dir=disk_episode)
    disk_observation, _ = env.reset(seed=42, config={
        "episode_dir": disk_episode,
        "generation": {"invalid_option_ignored_for_directory": True},
    })
    assert disk_observation["manifest_summary"]["episode_id"] == "disk_episode"
    generated, _ = env.reset(seed=42, config={"error_types": []})
    assert generated["manifest_summary"]["episode_id"] == "generated_episode"
    assert env.truth_file.issues == []
    assert env.reset()[0] == disk_observation


def test_reset_mode_only_generates_default_and_clean_configuration():
    env = FinancialAuditEnv()
    first, _ = env.reset(config={"mode": "eval"})
    assert first == FinancialAuditEnv(mode="eval").reset(seed=0)[0]
    env.reset(seed=95, config={"generation": {"clean_mode": True}})
    assert not env.truth_file.issues


def test_generated_eval_oracle_submission_hides_metrics():
    env = FinancialAuditEnv(mode="eval")
    env.reset(seed=215, config={"error_types": ["X1", "X2", "E1", "E2", "E3", "E4"]})
    findings = [{
        "type": issue.type,
        "affected_ids": issue.affected_ids,
        "claimed_amount_minor": issue.expected_amount_minor,
        "currency": issue.currency,
        "evidence_ids": issue.acceptable_evidence_sets[0],
    } for issue in env.truth_file.issues]
    observation, reward, terminated, truncated, info = env.step({"type": "submit", "findings": findings})
    assert reward == 0.0 and terminated and not truncated
    assert info == {"eval_metrics": {}}
    assert env.evaluator_reward == pytest.approx(0.998)
    assert env.evaluator_metrics["tp"] == len(findings)
    assert "acceptable_evidence_sets" not in json.dumps(observation)


@pytest.mark.parametrize("action", [None, {}, "invalid", {"type": []}])
@pytest.mark.parametrize("mode, expected_reward", [("train", -1.0), ("eval", 0.0)])
def test_invalid_final_action_uses_same_timeout_penalty(action, mode, expected_reward):
    env = FinancialAuditEnv(max_steps=1, mode=mode)
    env.reset(seed=8, config={"error_types": []})
    observation, reward, terminated, truncated, info = env.step(action)
    assert reward == expected_reward and not terminated and truncated
    assert observation["remaining_steps"] == 0
    assert env.evaluator_reward == -1.0
    assert info["eval_metrics"] == ({} if mode == "eval" else env.evaluator_metrics)
    with pytest.raises(RuntimeError):
        env.step({"type": "submit", "findings": []})


@pytest.mark.parametrize("budget", [0, -1, 101, True, 1.5])
def test_step_budget_cannot_exceed_contract(budget):
    with pytest.raises(ValueError):
        FinancialAuditEnv(max_steps=budget)


def test_invalid_mode_or_failed_reset_cannot_reuse_previous_data():
    with pytest.raises(ValueError):
        FinancialAuditEnv(mode="evaluaton")
    env = FinancialAuditEnv()
    with pytest.raises(RuntimeError):
        env.step({"type": "calculator", "expression": "1+1"})
    env.reset(seed=20)
    with pytest.raises(ValueError):
        env.reset(seed=20, config={"mode": "typo"})
    assert env.action_handler is None and env.truth_file is None
    with pytest.raises(RuntimeError):
        env.step({"type": "submit", "findings": []})


@pytest.mark.parametrize("action", [
    {"type": "get_document", "doc_id": "../truth.json"},
    {"type": "get_document", "doc_id": "C:/private/provenance.json"},
    {"type": "get_record", "table": "truth.json", "id": "private-marker"},
    {"type": "list_records", "table": "C:/private/provenance.json"},
    {"type": "calculator", "expression": "open('C:/private/truth.json').read()"},
    {"type": "submit", "findings": [{"private-marker": "C:/private/truth.json"}]},
])
def test_errors_never_echo_protected_file_names_paths_or_validation_payload(action):
    env = FinancialAuditEnv()
    env.reset(seed=42)
    result = env.step(action)
    serialized = json.dumps(result)
    assert "private-marker" not in serialized
    assert "truth.json" not in serialized and "provenance.json" not in serialized
    assert "C:/private" not in serialized and "acceptable_evidence_sets" not in serialized


def test_initial_and_step_observations_hide_private_metadata():
    env = FinancialAuditEnv()
    initial, info = env.reset(seed=987654321)
    env.policy_data["seed"] = 987654321
    env.policy_data["private_path"] = "private-marker"
    step = env.step({"type": "list_records", "table": "ledger", "limit": 1})
    serialized = json.dumps([initial, info, step])
    assert "seed" not in serialized and "private-marker" not in serialized
    assert "987654321" not in serialized and "issue_id" not in serialized


def test_fx_list_and_get_share_stable_natural_identifier():
    env = FinancialAuditEnv()
    env.reset(seed=42)
    observation, *_ = env.step({"type": "list_records", "table": "fx", "limit": 500})
    quotes = observation["action_result"]["records"]
    assert len(quotes) == 50
    quote = quotes[0]
    assert quote["id"] == fx_record_id(quote["date"], quote["source_currency"], quote["target_currency"])
    retrieved, *_ = env.step({"type": "get_record", "table": "fx", "id": quote["id"]})
    assert retrieved["action_result"]["record"] == quote
    reordered = ActionHandler([], {}, {}, list(reversed(quotes)))
    assert reordered.get_record("fx", quote["id"])["record"] == quote
    for action in (
        {"type": "get_record", "table": "fx", "id": "missing"},
        {"type": "get_record", "table": "invalid", "id": quote["id"]},
    ):
        previous_step = env.current_step
        result = env.step(action)
        assert result[0]["error"] and result[0]["step"] == previous_step + 1
        assert result[1] == 0.0


def test_fx_duplicate_natural_key_is_rejected():
    quote = {"date": "2025-01-01", "source_currency": "EUR", "target_currency": "USD", "rate": "1.1"}
    with pytest.raises(ValueError, match="unique"):
        ActionHandler([], {}, {}, [quote, quote])


def test_public_records_are_detached_copies():
    env = FinancialAuditEnv()
    env.reset(seed=42)
    result = env.action_handler.list_records("ledger", limit=1)
    record = result["records"][0]
    row_id, amount = record["row_id"], record["debit_minor"]
    record["debit_minor"] = amount + 100
    assert env.action_handler.get_record("ledger", row_id)["record"]["debit_minor"] == amount
    document = next(iter(env.action_handler.payments.values()))
    copied = env.action_handler.get_document(document["doc_id"])
    copied["document"]["invoice_refs"].clear()
    assert env.action_handler.get_document(document["doc_id"])["document"]["invoice_refs"]


def test_csv_null_and_legacy_blank_read_as_json_null(disk_episode):
    path = disk_episode / "ledger.csv"
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields = reader.fieldnames
        rows = list(reader)
    for row in rows:
        for key in ("entity_id", "invoice_id", "payment_id"):
            if row[key] in ("", "null"):
                row[key] = "null"
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fields)
        writer.writeheader()
        writer.writerows(rows)
    explicit = FinancialAuditEnv(disk_episode)
    explicit.reset()
    expected = public_snapshot(explicit)
    assert any(row["invoice_id"] is None for row in expected[0])
    assert not any(row[key] == "null" for row in expected[0] for key in ("entity_id", "invoice_id", "payment_id"))
    for row in rows:
        for key in ("entity_id", "invoice_id", "payment_id"):
            if row[key] == "null":
                row[key] = ""
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fields)
        writer.writeheader()
        writer.writerows(rows)
    legacy = FinancialAuditEnv(disk_episode)
    legacy.reset()
    assert public_snapshot(legacy) == expected


def test_calculator_preserves_decimal_literal_and_ignores_ambient_precision():
    with localcontext() as context:
        context.prec = 3
        assert safe_eval_expression("0.12345678901234567890123456789 + 0") == Decimal("0.12345678901234567890123456789")
        assert safe_eval_expression("123.45 + 67.89") == Decimal("191.34")


@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo unsafe')", "open('truth.json')", "(1).__class__", "[1][0]",
    "'1.2' + '3.4'", "True + 1", "2 ** 10", "1 / 0", "1e1001", "1e-1001",
    "1+" * 3000 + "1", "+".join(["1"] * 100),
])
def test_calculator_rejects_code_and_unbounded_input(expression):
    with pytest.raises(ValueError):
        safe_eval_expression(expression)


def test_generated_configuration_is_reproducible_and_invalid_options_fail():
    config = {"generation": {"num_cycles": 20, "cycle_types": ["unpaid"]}, "error_types": []}
    left, right = FinancialAuditEnv(), FinancialAuditEnv()
    assert left.reset(seed=601, config=config) == right.reset(seed=601, config=config)
    assert public_snapshot(left) == public_snapshot(right)
    with pytest.raises(ValueError):
        left.reset(seed=601, config={"generation": {"unknown_parameter": True}})
    with pytest.raises(ValueError):
        left.reset(seed=True)


@pytest.mark.parametrize("mode, expected_reward", [("train", -1.0), ("eval", 0.0)])
def test_missing_truth_clears_stale_evaluator_and_still_penalizes_malformed_submit(disk_episode, tmp_path, mode, expected_reward):
    import shutil

    public_directory = tmp_path / "without_truth"
    public_directory.mkdir()
    for source in disk_episode.iterdir():
        if source.name != "truth.json":
            shutil.copyfile(source, public_directory / source.name)
    env = FinancialAuditEnv(disk_episode, mode=mode)
    env.reset()
    assert env.truth_file is not None
    env.step({"type": "submit", "findings": []})
    env.reset(config={"episode_dir": public_directory})
    assert env.truth_file is None and env.evaluator_metrics == {} and env.evaluator_reward == 0.0
    observation, reward, terminated, truncated, info = env.step({"type": "submit", "findings": [{"broken": "private-marker"}]})
    assert terminated and not truncated and reward == expected_reward
    assert env.evaluator_reward == -1.0
    assert info["eval_metrics"] == ({} if mode == "eval" else {"reward": -1.0})
    assert "private-marker" not in json.dumps(observation)
