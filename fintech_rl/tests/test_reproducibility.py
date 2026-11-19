import hashlib
import json
import csv
from pathlib import Path
import pytest
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile
from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.policies.oracle import OraclePolicy
from fintech_rl.scoring.matcher import canonicalize_ids, match_findings_to_truth


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def test_bit_exact_reproducibility_and_hashes(tmp_path):
    """
    Two complete runs with identical seed, config, actions give:
    1. Bitwise identical files on disk (exact SHA-256 hash match).
    2. Identical observation transitions and rewards.
    """
    ep_dir1 = tmp_path / "run1"
    ep_dir2 = tmp_path / "run2"

    seed = 8888
    # Run 1
    c1 = SyntheticCompany(seed=seed, episode_id="repro_test")
    c1.generate()
    inj1 = ErrorInjector(c1, seed=seed)
    inj1.apply_errors(["E1", "E3"])
    t1 = TruthFile(episode_id="repro_test", issues=inj1.issues)
    p1 = create_provenance_file("repro_test", seed, inj1.changes)
    render_episode_files(c1, t1, p1, ep_dir1)

    # Run 2
    c2 = SyntheticCompany(seed=seed, episode_id="repro_test")
    c2.generate()
    inj2 = ErrorInjector(c2, seed=seed)
    inj2.apply_errors(["E1", "E3"])
    t2 = TruthFile(episode_id="repro_test", issues=inj2.issues)
    p2 = create_provenance_file("repro_test", seed, inj2.changes)
    render_episode_files(c2, t2, p2, ep_dir2)

    # Verify SHA-256 bitwise match for all rendered files
    filenames = ["manifest.json", "policy.json", "ledger.csv", "invoices.jsonl", "payments.jsonl", "fx.csv", "truth.json", "provenance.json"]
    for fn in filenames:
        hash1 = file_sha256(ep_dir1 / fn)
        hash2 = file_sha256(ep_dir2 / fn)
        assert hash1 == hash2, f"Bitwise SHA-256 mismatch for file {fn}"

    # Verify identical transitions and rewards in environment
    actions = [
        {"type": "list_records", "table": "ledger", "limit": 10},
        {"type": "calculator", "expression": "5000 + 200"},
        {"type": "submit", "findings": []}
    ]

    env1 = FinancialAuditEnv(episode_dir=ep_dir1)
    env2 = FinancialAuditEnv(episode_dir=ep_dir2)
    obs1, info1 = env1.reset()
    obs2, info2 = env2.reset()
    assert obs1 == obs2

    for act in actions:
        o1, r1, t1, tr1, i1 = env1.step(act)
        o2, r2, t2, tr2, i2 = env2.step(act)
        assert o1 == o2
        assert r1 == r2
        assert t1 == t2
        assert tr1 == tr2
        assert i1 == i2


def test_row_permutation_and_id_remap_preserves_oracle_reward(tmp_path):
    """
    Permuting row order and consistently remapping IDs preserves:
    - Matcher TP recognition (due to canonical set comparison).
    - Oracle response validity and reward with updated IDs.
    """
    ep_dir = tmp_path / "permuted_ep"
    seed = 999
    c = SyntheticCompany(seed=seed, episode_id="permuted_ep")
    c.generate()
    inj = ErrorInjector(c, seed=seed)
    inj.inject_e1_duplicate_accounts()
    t = TruthFile(episode_id="permuted_ep", issues=inj.issues)
    p = create_provenance_file("permuted_ep", seed, inj.changes)
    render_episode_files(c, t, p, ep_dir)

    # Base oracle run
    env_orig = FinancialAuditEnv(episode_dir=ep_dir)
    env_orig.reset()
    oracle_orig = OraclePolicy(episode_dir=ep_dir)
    act_orig = oracle_orig.act(None)
    _, reward_orig, _, _, info_orig = env_orig.step(act_orig)
    assert reward_orig > 0.99

    # Now simulate ID remapping: ROW-00001 -> ROW-RENAMED-00001 in open files and truth
    id_map = {}
    for r in c.ledger:
        id_map[r.row_id] = r.row_id.replace("ROW-", "RENAMED-ROW-")
    for inv in c.invoices:
        id_map[inv.invoice_id] = inv.invoice_id.replace("INV-", "RENAMED-INV-")
        id_map[inv.doc_id] = inv.doc_id.replace("DOC-", "RENAMED-DOC-")

    # Remap truth
    remap_dir = tmp_path / "remapped_ep"
    for r in c.ledger:
        r.row_id = id_map.get(r.row_id, r.row_id)
        if r.invoice_id in id_map:
            r.invoice_id = id_map[r.invoice_id]
    # Reverse ledger row order (permutation)
    c.ledger.reverse()

    for inv in c.invoices:
        inv.invoice_id = id_map.get(inv.invoice_id, inv.invoice_id)
        inv.doc_id = id_map.get(inv.doc_id, inv.doc_id)

    remapped_issues = []
    for issue in t.issues:
        new_aff = [id_map.get(x, x) for x in issue.affected_ids]
        # Reverse affected IDs order to test set canonicalization
        new_aff.reverse()
        new_ev_sets = [[id_map.get(x, x) for x in ev_set] for ev_set in issue.acceptable_evidence_sets]
        remapped_issues.append(issue.model_copy(update={
            "affected_ids": new_aff,
            "acceptable_evidence_sets": new_ev_sets
        }))
    remapped_truth = TruthFile(episode_id="remapped_ep", issues=remapped_issues)

    render_episode_files(c, remapped_truth, p, remap_dir)

    # Oracle run on remapped & permuted episode
    env_remap = FinancialAuditEnv(episode_dir=remap_dir)
    env_remap.reset()
    oracle_remap = OraclePolicy(episode_dir=remap_dir)
    act_remap = oracle_remap.act(None)
    _, reward_remap, _, _, info_remap = env_remap.step(act_remap)

    assert reward_remap == reward_orig
    assert info_remap["eval_metrics"]["tp"] == info_orig["eval_metrics"]["tp"]
    assert info_remap["eval_metrics"]["f1"] == info_orig["eval_metrics"]["f1"]
