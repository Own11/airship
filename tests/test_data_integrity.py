"""Artifact round trips and independent validator falsification tests."""
import csv
import json
from collections import defaultdict

import pytest

from fintech_rl.env.environment import FinancialAuditEnv
from fintech_rl.generator.documents import render_episode_files
from fintech_rl.generator.episode import generate_episode
from fintech_rl.generator.validator import validate_episode_truth
from fintech_rl.policies.simple_reconciler import SimpleReconcilerPolicy
from fintech_rl.scoring.tolerances import convert_fx
from decimal import Decimal


@pytest.fixture
def episode(tmp_path):
    company, truth, provenance = generate_episode(98761, error_types=['E1', 'E2', 'E3', 'E4', 'X1', 'X2'])
    render_episode_files(company, truth, provenance, tmp_path)
    assert validate_episode_truth(tmp_path) == []
    return tmp_path, company, truth, provenance


def test_csv_explicit_null_and_legacy_round_trip(tmp_path):
    company, truth, provenance = generate_episode(619, error_types=[])
    render_episode_files(company, truth, provenance, tmp_path)
    path = tmp_path / 'ledger.csv'
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    assert any(row['invoice_id'] == 'null' for row in rows)
    assert all(row[field] != '' for row in rows for field in ('entity_id', 'invoice_id', 'payment_id'))
    env = FinancialAuditEnv(tmp_path)
    env.reset()
    expected = [row.model_dump() for row in company.ledger]
    actual = []
    cursor = 0
    while True:
        obs, reward, terminated, truncated, _ = env.step({'type': 'list_records', 'table': 'ledger', 'cursor': cursor})
        result = obs['action_result']
        actual.extend(result['records'])
        cursor = result['next_cursor']
        if cursor is None:
            break
    assert actual == expected
    path.write_text(path.read_text(encoding='utf-8').replace(',null', ','), encoding='utf-8')
    env.reset()
    assert env.action_handler.ledger == expected
    assert all(row.get('payment_id') != 'null' for row in env.action_handler.ledger)
    assert validate_episode_truth(tmp_path) == []


@pytest.mark.parametrize('kind', ['count', 'balance', 'amount', 'currency', 'evidence', 'provenance', 'fx', 'period', 'clean_payment'])
def test_validator_detects_real_corruption(episode, kind):
    directory, company, truth, provenance = episode
    if kind == 'count':
        path = directory / 'manifest.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        payload['n_records'] += 1
        path.write_text(json.dumps(payload), encoding='utf-8')
    elif kind in ('balance', 'period', 'clean_payment'):
        if kind == 'balance':
            company.ledger[0].debit_minor += 1 if company.ledger[0].debit_minor else 0
            company.ledger[0].credit_minor += 1 if company.ledger[0].credit_minor else 0
        elif kind == 'period':
            issue = next(issue for issue in truth.issues if issue.type == 'period_misclassification')
            invoice = next(inv for inv in company.invoices if inv.invoice_id in issue.affected_ids)
            for row in company.ledger:
                if row.row_id in issue.affected_ids:
                    row.timestamp = invoice.issued_at
        else:
            changed = {identifier for issue in truth.issues for identifier in issue.affected_ids}
            pay = next(pay for pay in company.payments if pay.payment_id not in changed)
            for row in company.ledger:
                if row.payment_id == pay.payment_id:
                    if row.debit_minor:
                        row.debit_minor += 10
                    else:
                        row.credit_minor += 10
        render_episode_files(company, truth, provenance, directory)
    elif kind in ('amount', 'currency', 'evidence'):
        path = directory / 'truth.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        if kind == 'amount':
            payload['issues'][0]['expected_amount_minor'] += 5
        elif kind == 'currency':
            payload['issues'][0]['currency'] = 'JPY'
        else:
            payload['issues'][0]['acceptable_evidence_sets'] = [['MISSING-DOCUMENT']]
        path.write_text(json.dumps(payload), encoding='utf-8')
    elif kind == 'provenance':
        path = directory / 'provenance.json'
        payload = json.loads(path.read_text(encoding='utf-8'))
        payload['changes'][0]['expected_amount_minor'] += 1
        path.write_text(json.dumps(payload), encoding='utf-8')
    else:
        path = directory / 'fx.csv'
        with path.open(encoding='utf-8', newline='') as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            row['rate'] = '2.5'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=['date', 'source_currency', 'target_currency', 'rate'])
            writer.writeheader()
            writer.writerows(rows)
    assert validate_episode_truth(directory), kind


def test_validator_is_independent_of_row_and_id_order(episode):
    directory, company, truth, provenance = episode
    company.ledger.reverse()
    remap = {}
    for index, row in enumerate(company.ledger):
        remap[row.row_id] = f'OPAQUE-{index:05d}'
        row.row_id = remap[row.row_id]
    for issue, change in zip(truth.issues, provenance.changes):
        issue.affected_ids = [remap.get(value, value) for value in reversed(issue.affected_ids)]
        issue.acceptable_evidence_sets = [[remap.get(value, value) for value in reversed(evidence)]
                                         for evidence in issue.acceptable_evidence_sets]
        change.affected_ids = issue.affected_ids[:]
        change.acceptable_evidence_sets = [values[:] for values in issue.acceptable_evidence_sets]
    render_episode_files(company, truth, provenance, directory)
    assert validate_episode_truth(directory) == []


@pytest.mark.parametrize('errors', [[], ['E1'], ['X2']])
def test_reconciler_uses_public_complete_duplicate_evidence(tmp_path, errors):
    company, truth, provenance = generate_episode(101, error_types=errors)
    render_episode_files(company, truth, provenance, tmp_path)
    env = FinancialAuditEnv(tmp_path)
    obs, _ = env.reset()
    policy = SimpleReconcilerPolicy()
    for _ in range(100):
        obs, reward, terminated, truncated, info = env.step(policy.act(obs))
        if terminated or truncated:
            break
    assert terminated and not truncated
    metrics = info['eval_metrics']
    assert metrics['fp'] == 0
    assert metrics['tp'] == (1 if errors else 0)
    assert metrics['fn'] == (1 if errors == ['X2'] else 0)


def test_decimal_fx_half_minor_unit_rounding():
    assert convert_fx(1, Decimal('1.5')) == 2
    assert convert_fx(1, Decimal('1.5'), 'ROUND_HALF_EVEN') == 2
    assert convert_fx(5, Decimal('0.5')) == 3
    assert convert_fx(5, Decimal('0.5'), 'ROUND_HALF_EVEN') == 2
    assert convert_fx(123456789, Decimal('1.123456789')) == 138698368

@pytest.mark.parametrize('field', ['manifest', 'invoice', 'payment', 'naive'])
def test_validator_reports_bad_dates_without_crashing(tmp_path, field):
    company, truth, provenance = generate_episode(998, error_types=[])
    if field == 'manifest':
        company.manifest.period_start = 'bad-date'
    elif field == 'invoice':
        company.invoices[0].issued_at = 'bad-date'
    elif field == 'payment':
        company.payments[0].timestamp = 'bad-date'
    else:
        company.invoices[0].issued_at = '2025-01-02T10:00:00'
    render_episode_files(company, truth, provenance, tmp_path)
    assert any('timestamp' in error for error in validate_episode_truth(tmp_path))


def test_validator_detects_unreported_period_on_clean_company(tmp_path):
    company, truth, provenance = generate_episode(234, error_types=[])
    invoice = company.invoices[0]
    for row in company.ledger:
        if row.invoice_id == invoice.invoice_id and row.payment_id is None:
            row.timestamp = '2025-02-01T00:00:00+00:00'
    render_episode_files(company, truth, provenance, tmp_path)
    assert any('Unreported period' in error for error in validate_episode_truth(tmp_path))


def test_validator_rejects_unrelated_postings_in_claim(episode):
    directory, company, truth, provenance = episode
    issue = next(issue for issue in truth.issues if issue.type == 'duplicate_accounts')
    row = next(row for row in company.ledger if row.row_id in issue.affected_ids)
    other = next(inv for inv in company.invoices if inv.invoice_id not in issue.affected_ids)
    row.invoice_id = other.invoice_id
    row.entity_id = other.entity_id
    render_episode_files(company, truth, provenance, directory)
    assert any('declared invoice' in error for error in validate_episode_truth(directory))


def test_artifacts_use_platform_independent_lf_and_private_reproduction_metadata(tmp_path):
    configuration = {'num_cycles': 20, 'cycle_types': ['unpaid']}
    company, truth, provenance = generate_episode(123, error_types=[], generation=configuration)
    paths = render_episode_files(company, truth, provenance, tmp_path)
    assert all(b'\r\n' not in path.read_bytes() for path in paths.values())
    assert provenance.generator_version == '2.0.0'
    assert provenance.generation_config == configuration
    assert provenance.error_types == []
    replica = generate_episode(provenance.seed, provenance.episode_id,
                               provenance.error_types, provenance.generation_config)
    assert replica[0].ledger == company.ledger
    env = FinancialAuditEnv(tmp_path)
    public = json.dumps(env.reset())
    assert 'generator_version' not in public and 'generation_config' not in public


def test_seed_reproduction_is_independent_of_process_hash_order():
    import os
    from pathlib import Path
    import subprocess
    import sys
    code = '''import hashlib, json
from fintech_rl.generator.episode import generate_episode
company,truth,provenance=generate_episode(87654,error_types=['X1','X2','E1','E2','E3','E4'])
payload=[company.manifest.model_dump(),[row.model_dump() for row in company.ledger],
 [doc.model_dump() for doc in company.invoices],[doc.model_dump() for doc in company.payments],
 [quote.model_dump(mode='json') for quote in company.fx_rates],truth.model_dump(),provenance.model_dump()]
print(hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest())'''
    digests = []
    for hash_seed in ('0', '17', 'random'):
        environment = dict(os.environ, PYTHONHASHSEED=hash_seed)
        result = subprocess.run([sys.executable, '-c', code], check=True,
                                cwd=Path(__file__).resolve().parents[1], env=environment,
                                capture_output=True, text=True, timeout=20)
        digests.append(result.stdout.strip())
    assert len(set(digests)) == 1
