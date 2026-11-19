import json
import pytest
from pathlib import Path
from fintech_rl.generator.company import SyntheticCompany
from fintech_rl.generator.errors import ErrorInjector
from fintech_rl.generator.provenance import create_provenance_file
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.schema import TruthFile
from fintech_rl.env.environment import FinancialAuditEnv


@pytest.fixture(scope="module")
def shared_episode(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("env_tests")
    ep_dir = tmp_path / "shared_ep"
    c = SyntheticCompany(seed=1234, episode_id="shared_ep")
    c.generate()
    inj = ErrorInjector(c, seed=1234)
    inj.inject_e1_duplicate_accounts()
    truth = TruthFile(episode_id="shared_ep", issues=inj.issues)
    prov = create_provenance_file("shared_ep", 1234, inj.changes)
    render_episode_files(c, truth, prov, ep_dir)
    return ep_dir


# 1. Reset tests
def test_01_reset_returns_tuple(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    res = env.reset()
    assert isinstance(res, tuple) and len(res) == 2


def test_02_reset_obs_json_serializable(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, info = env.reset()
    dumped = json.dumps(obs)
    assert isinstance(dumped, str)


def test_03_reset_info_json_serializable(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, info = env.reset()
    dumped = json.dumps(info)
    assert isinstance(dumped, str)


def test_04_reset_remaining_steps(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode, max_steps=100)
    obs, _ = env.reset()
    assert obs["remaining_steps"] == 100
    assert obs["step"] == 0


def test_05_reset_initial_status(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, _ = env.reset()
    assert obs["action_result"] == {"status": "episode_started"}
    assert obs["error"] is None


# 2. Step contract tests
def test_06_step_returns_5_tuple(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    step_res = env.step({"type": "calculator", "expression": "1+1"})
    assert isinstance(step_res, tuple) and len(step_res) == 5


def test_07_step_tuple_types(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, reward, term, trunc, info = env.step({"type": "calculator", "expression": "1+1"})
    assert isinstance(obs, dict)
    assert isinstance(reward, float)
    assert isinstance(term, bool)
    assert isinstance(trunc, bool)
    assert isinstance(info, dict)


def test_08_step_obs_json_serializable(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "1+1"})
    assert json.dumps(obs)


def test_09_step_decrements_remaining(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode, max_steps=100)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "1+1"})
    assert obs["remaining_steps"] == 99
    assert obs["step"] == 1


def test_10_interim_reward_is_zero(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    _, r1, _, _, _ = env.step({"type": "list_records", "table": "ledger", "limit": 10})
    _, r2, _, _, _ = env.step({"type": "calculator", "expression": "100+200"})
    assert r1 == 0.0
    assert r2 == 0.0


# 3. Termination & Truncation
def test_11_submit_causes_terminated(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    _, reward, term, trunc, _ = env.step({"type": "submit", "findings": []})
    assert term is True
    assert trunc is False


def test_12_step_after_terminated_raises(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    env.step({"type": "submit", "findings": []})
    with pytest.raises(RuntimeError):
        env.step({"type": "calculator", "expression": "1+1"})


def test_13_timeout_exhaustion_at_max_steps(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode, max_steps=3)
    env.reset()
    _, _, t1, tr1, _ = env.step({"type": "calculator", "expression": "1+1"})
    assert not t1 and not tr1
    _, _, t2, tr2, _ = env.step({"type": "calculator", "expression": "1+1"})
    assert not t2 and not tr2
    obs3, reward, t3, tr3, info = env.step({"type": "calculator", "expression": "1+1"})
    assert not t3
    assert tr3 is True
    assert reward == -1.0
    assert obs3["action_result"] == {}


def test_14_step_after_truncated_raises(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode, max_steps=2)
    env.reset()
    env.step({"type": "calculator", "expression": "1+1"})
    env.step({"type": "calculator", "expression": "1+1"})
    with pytest.raises(RuntimeError):
        env.step({"type": "calculator", "expression": "1+1"})


# 4. Action: list_records & pagination
def test_15_list_records_ledger(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 10})
    res = obs["action_result"]
    assert res["table"] == "ledger"
    assert len(res["records"]) == 10
    assert res["next_cursor"] == 10


def test_16_list_records_limit_capped_at_50(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 500})
    res = obs["action_result"]
    assert len(res["records"]) == 50
    assert res["limit"] == 50


def test_17_list_records_cursor_stability(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs1, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 20})
    obs2, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 20})
    assert obs1["action_result"]["records"] == obs2["action_result"]["records"]


def test_18_list_records_pagination_sequence(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs1, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 0, "limit": 15})
    obs2, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "cursor": 15, "limit": 15})
    ids1 = [r["row_id"] for r in obs1["action_result"]["records"]]
    ids2 = [r["row_id"] for r in obs2["action_result"]["records"]]
    assert len(set(ids1).intersection(set(ids2))) == 0


def test_19_list_records_fx_table(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "list_records", "table": "fx", "limit": 5})
    assert obs["action_result"]["table"] == "fx"
    assert len(obs["action_result"]["records"]) == 5


def test_20_list_records_invoices_table(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "list_records", "table": "invoices", "limit": 5})
    assert obs["action_result"]["table"] == "invoices"
    assert len(obs["action_result"]["records"]) == 5


def test_21_list_records_payments_table(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "list_records", "table": "payments", "limit": 5})
    assert obs["action_result"]["table"] == "payments"
    assert len(obs["action_result"]["records"]) == 5


def test_22_list_records_unknown_table_burns_step(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, r, term, trunc, _ = env.step({"type": "list_records", "table": "secret_table"})
    assert obs["error"] is not None
    assert "Unknown table" in obs["error"]
    assert obs["step"] == 1


# 5. Action: get_record & get_document
def test_23_get_record_existing_ledger(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs1, _, _, _, _ = env.step({"type": "list_records", "table": "ledger", "limit": 1})
    row_id = obs1["action_result"]["records"][0]["row_id"]
    obs2, _, _, _, _ = env.step({"type": "get_record", "table": "ledger", "id": row_id})
    assert obs2["action_result"]["record"]["row_id"] == row_id


def test_24_get_record_invalid_id_burns_step(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "get_record", "table": "ledger", "id": "MISSING_ROW_999"})
    assert "not found" in obs["error"]
    assert obs["step"] == 1


def test_25_get_document_existing_invoice(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs1, _, _, _, _ = env.step({"type": "list_records", "table": "invoices", "limit": 1})
    doc_id = obs1["action_result"]["records"][0]["doc_id"]
    obs2, _, _, _, _ = env.step({"type": "get_document", "doc_id": doc_id})
    assert obs2["action_result"]["doc_type"] == "invoice"
    assert obs2["action_result"]["document"]["doc_id"] == doc_id


def test_26_get_document_existing_payment(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs1, _, _, _, _ = env.step({"type": "list_records", "table": "payments", "limit": 1})
    doc_id = obs1["action_result"]["records"][0]["doc_id"]
    obs2, _, _, _, _ = env.step({"type": "get_document", "doc_id": doc_id})
    assert obs2["action_result"]["doc_type"] == "payment"
    assert obs2["action_result"]["document"]["doc_id"] == doc_id


def test_27_get_document_invalid_doc_id(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "get_document", "doc_id": "NON_EXISTENT_DOC"})
    assert "not found" in obs["error"]
    assert obs["step"] == 1


# 6. Action: calculator
def test_28_calculator_addition(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "123.45 + 67.89"})
    assert obs["action_result"]["result"] == "191.34"


def test_29_calculator_multiplication(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "15 * 25"})
    assert obs["action_result"]["result"] == "375"


def test_30_calculator_disallow_import(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "__import__('os').system('ls')"})
    assert obs["error"] is not None
    assert "Disallowed" in obs["error"] or "error" in obs["error"]


def test_31_calculator_disallow_variables(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "x + 1"})
    assert obs["error"] is not None


def test_32_calculator_disallow_strings(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "calculator", "expression": "'hello' + 'world'"})
    assert obs["error"] is not None


# 7. Invalid actions & error handling
def test_33_invalid_action_non_dict(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, r, term, trunc, info = env.step("not a dict")
    assert obs["error"] is not None
    assert obs["step"] == 1


def test_34_invalid_action_missing_type(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, r, term, trunc, info = env.step({"foo": "bar"})
    assert obs["error"] is not None
    assert obs["step"] == 1


def test_35_unknown_action_type(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, r, term, trunc, info = env.step({"type": "drop_tables"})
    assert "Unknown action type" in obs["error"]
    assert obs["step"] == 1


# 8. State isolation between episodes
def test_36_state_isolation_between_resets(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode, max_steps=50)
    env.reset()
    env.step({"type": "calculator", "expression": "1+1"})
    env.step({"type": "calculator", "expression": "2+2"})
    assert env.current_step == 2

    # Reset
    obs, _ = env.reset()
    assert env.current_step == 0
    assert obs["step"] == 0
    assert obs["remaining_steps"] == 50
    assert env.is_terminated is False
    assert env.is_truncated is False


def test_37_two_separate_env_instances_isolated(shared_episode):
    env1 = FinancialAuditEnv(episode_dir=shared_episode)
    env2 = FinancialAuditEnv(episode_dir=shared_episode)
    env1.reset()
    env2.reset()
    env1.step({"type": "calculator", "expression": "1+1"})
    assert env1.current_step == 1
    assert env2.current_step == 0


# 9. Information security: Zero leak tests
def test_38_no_truth_filename_in_obs(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, _ = env.reset()
    assert "truth.json" not in json.dumps(obs)


def test_39_no_provenance_filename_in_obs(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, _ = env.reset()
    assert "provenance.json" not in json.dumps(obs)


def test_40_no_seed_in_obs(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    obs, _ = env.reset()
    assert "seed" not in obs
    assert "seed" not in json.dumps(obs["manifest_summary"])


def test_41_no_truth_leak_in_error_message(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    obs, _, _, _, _ = env.step({"type": "get_record", "table": "ledger", "id": "truth.json"})
    assert "truth.json" not in obs.get("error", "").replace("truth.json", "")
    assert "acceptable_evidence_sets" not in json.dumps(obs)


def test_42_no_truth_leak_in_eval_metrics(shared_episode):
    env = FinancialAuditEnv(episode_dir=shared_episode)
    env.reset()
    _, _, _, _, info = env.step({"type": "submit", "findings": []})
    metrics_str = json.dumps(info)
    assert "issue_id" not in metrics_str
    assert "acceptable_evidence_sets" not in metrics_str
    assert "provenance" not in metrics_str
