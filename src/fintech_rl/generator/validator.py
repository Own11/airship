"""Reproduce ground truth from public artifacts and verify accounting integrity."""
import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from fintech_rl.generator.company import ACCOUNTS
from fintech_rl.identifiers import fx_record_id
from fintech_rl.schema import (Manifest, LedgerRow, InvoiceDoc, PaymentDoc, TruthFile,
                               ProvenanceFile, FXRateRow)
from fintech_rl.scoring.tolerances import convert_fx


def validate_episode_truth(episode_dir: Path) -> list[str]:
    """Check sizes, references, balances, evidence and independently derived amounts.

    Identifiers are opaque: no validation depends on an ID prefix or row order.
    This function is evaluator-only and never called through the agent API.
    """
    directory = Path(episode_dir)
    errors: list[str] = []
    try:
        manifest = Manifest.model_validate_json((directory / 'manifest.json').read_text(encoding='utf-8'))
        truth = TruthFile.model_validate_json((directory / 'truth.json').read_text(encoding='utf-8'))
        provenance = ProvenanceFile.model_validate_json((directory / 'provenance.json').read_text(encoding='utf-8'))
        with (directory / 'ledger.csv').open(encoding='utf-8', newline='') as stream:
            raw_rows = list(csv.DictReader(stream))
        for row in raw_rows:
            for name in ('entity_id', 'invoice_id', 'payment_id'):
                if row[name] in ('', 'null'):
                    row[name] = None
        ledger = [LedgerRow.model_validate(row) for row in raw_rows]
        invoices = [InvoiceDoc.model_validate_json(line) for line in
                    (directory / 'invoices.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        payments = [PaymentDoc.model_validate_json(line) for line in
                    (directory / 'payments.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
        with (directory / 'fx.csv').open(encoding='utf-8', newline='') as stream:
            fx = [FXRateRow.model_validate(row) for row in csv.DictReader(stream)]
    except (OSError, ValueError, KeyError, ValidationError) as exc:
        return [f'Invalid episode artifacts: {exc}']

    # Validate every temporal input before ordering or comparing it. Report corrupt
    # artifacts instead of leaking an uncaught naive/aware datetime exception.
    timestamps = [manifest.period_start, manifest.period_end]
    timestamps += [row.timestamp for row in ledger]
    timestamps += [value for invoice in invoices for value in (invoice.issued_at, invoice.due_at)]
    timestamps += [pay.timestamp for pay in payments]
    for timestamp in timestamps:
        try:
            parsed = datetime.fromisoformat(timestamp)
            if parsed.utcoffset() is None:
                raise ValueError('timezone required')
        except (ValueError, TypeError):
            errors.append('Invalid or naive timestamp in episode artifacts')
            return errors
    if datetime.fromisoformat(manifest.period_start) > datetime.fromisoformat(manifest.period_end):
        return ['Reporting period start follows period end']

    if not 200 <= len(ledger) <= 2000:
        errors.append(f'Ledger count outside 200..2000: {len(ledger)}')
    if not 20 <= len(invoices) + len(payments) <= 200:
        errors.append(f'Document count outside 20..200: {len(invoices) + len(payments)}')
    if manifest.n_records != len(ledger) or manifest.n_documents != len(invoices) + len(payments):
        errors.append('Manifest counts do not match actual artifacts')
    if not 0 <= len(truth.issues) <= 12:
        errors.append('Issue count outside 0..12')
    if truth.episode_id != manifest.episode_id or provenance.episode_id != manifest.episode_id:
        errors.append('Episode identifiers disagree')

    def index_unique(values, field, label):
        index = {}
        for value in values:
            identifier = getattr(value, field)
            if identifier in index:
                errors.append(f'Duplicate {label} identifier: {identifier}')
            index[identifier] = value
        return index

    rows = index_unique(ledger, 'row_id', 'ledger')
    invs = index_unique(invoices, 'invoice_id', 'invoice')
    pays = index_unique(payments, 'payment_id', 'payment')
    docs = index_unique(invoices + payments, 'doc_id', 'document')
    rates = {}
    for rate in fx:
        key = fx_record_id(rate.date, rate.source_currency, rate.target_currency)
        if key in rates:
            errors.append(f'Duplicate FX key: {key}')
        if not rate.rate.is_finite() or rate.rate <= 0:
            errors.append(f'Invalid FX rate: {key}')
        rates[key] = rate.rate
    all_ids = set(rows) | set(invs) | set(pays) | set(docs) | set(rates)
    namespaces = [set(rows), set(invs), set(pays), set(docs), set(rates)]
    if sum(map(len, namespaces)) != len(all_ids):
        errors.append('Identifiers collide across public namespaces')

    balances = defaultdict(int)
    for row in ledger:
        key = (row.timestamp, row.currency, row.entity_id, row.invoice_id, row.payment_id)
        balances[key] += row.debit_minor - row.credit_minor
        if row.invoice_id is not None and row.invoice_id not in invs:
            errors.append(f'Unknown invoice reference on {row.row_id}')
        if row.payment_id is not None and row.payment_id not in pays:
            errors.append(f'Unknown payment reference on {row.row_id}')
        if row.invoice_id in invs and row.entity_id != invs[row.invoice_id].entity_id:
            errors.append(f'Entity differs from invoice on {row.row_id}')
        if row.payment_id in pays and row.invoice_id not in pays[row.payment_id].invoice_refs:
            errors.append(f'Ledger/payment invoice references disagree on {row.row_id}')
        try:
            if datetime.fromisoformat(row.timestamp).utcoffset() is None:
                errors.append(f'Naive timestamp on {row.row_id}')
        except ValueError:
            errors.append(f'Invalid timestamp on {row.row_id}')
    if any(balances.values()):
        errors.append('Unbalanced transaction/currency postings')

    for pay in payments:
        if not pay.invoice_refs or any(ref not in invs for ref in pay.invoice_refs):
            errors.append(f'Unknown or empty invoice references on {pay.payment_id}')
        for ref in pay.invoice_refs:
            if ref in invs:
                invoice = invs[ref]
                if pay.currency != invoice.currency:
                    errors.append(f'Payment/document currency differs on {pay.payment_id}')
                if datetime.fromisoformat(pay.timestamp) < datetime.fromisoformat(invoice.issued_at):
                    errors.append(f'Payment precedes invoice on {pay.payment_id}')
                if pay.direction == 'refund' and invoice.document_type != 'credit_note':
                    errors.append(f'Refund lacks credit note on {pay.payment_id}')
    for invoice in invoices:
        if datetime.fromisoformat(invoice.due_at) < datetime.fromisoformat(invoice.issued_at):
            errors.append(f'Invoice due date precedes issue date on {invoice.invoice_id}')
        if invoice.document_type == 'credit_note':
            original = invs.get(invoice.related_invoice_id)
            if original is None or original.document_type != 'invoice':
                errors.append(f'Credit note lacks original invoice on {invoice.invoice_id}')
            elif (invoice.currency != original.currency or invoice.entity_id != original.entity_id
                  or invoice.total_minor > original.total_minor
                  or datetime.fromisoformat(invoice.issued_at) < datetime.fromisoformat(original.issued_at)):
                errors.append(f'Invalid credit note relationship on {invoice.invoice_id}')

    # Cut-off errors must be explicitly reported, including corruption on a clean
    # company. Merely naming a row in an unrelated issue cannot conceal it.
    period_rows = {identifier for issue in truth.issues if issue.type == 'period_misclassification'
                   for identifier in issue.affected_ids}
    start, end = datetime.fromisoformat(manifest.period_start), datetime.fromisoformat(manifest.period_end)
    for row in ledger:
        if row.invoice_id in invs and row.payment_id is None:
            document_inside = start <= datetime.fromisoformat(invs[row.invoice_id].issued_at) <= end
            row_inside = start <= datetime.fromisoformat(row.timestamp) <= end
            if document_inside != row_inside and row.row_id not in period_rows:
                errors.append(f'Unreported period discrepancy: {row.row_id}')
        if row.payment_id in pays and row.timestamp != pays[row.payment_id].timestamp:
            errors.append(f'Payment/posting timestamp differs: {row.row_id}')
    for original in invoices:
        notes = [note for note in invoices if note.related_invoice_id == original.invoice_id]
        if sum(note.total_minor for note in notes) > original.total_minor:
            errors.append(f'Credit notes exceed original invoice: {original.invoice_id}')
        if original.document_type == 'credit_note':
            refunds = [pay for pay in payments if pay.direction == 'refund' and original.invoice_id in pay.invoice_refs]
            if sum(pay.amount_minor for pay in refunds) > original.total_minor:
                errors.append(f'Refunds exceed credit note: {original.invoice_id}')

    issue_ids = set()
    signatures = set()
    changed_rows = set()
    for issue in truth.issues:
        label = f'Issue {issue.issue_id}'
        if issue.issue_id in issue_ids:
            errors.append(f'{label}: duplicate issue identifier')
        issue_ids.add(issue.issue_id)
        signature = (issue.type, tuple(sorted(issue.affected_ids)))
        if signature in signatures:
            errors.append(f'{label}: duplicate truth claim')
        signatures.add(signature)
        if not issue.affected_ids or any(identifier not in all_ids for identifier in issue.affected_ids):
            errors.append(f'{label}: affected ID not found in open files')
        for evidence in issue.acceptable_evidence_sets:
            if not evidence or len(evidence) > 10 or any(identifier not in all_ids for identifier in evidence):
                errors.append(f'{label}: invalid or unavailable evidence')
        affected_rows = [rows[identifier] for identifier in issue.affected_ids if identifier in rows]
        changed_rows.update(row.row_id for row in affected_rows)
        affected_invoices = [invs[identifier] for identifier in issue.affected_ids if identifier in invs]
        affected_payments = [pays[identifier] for identifier in issue.affected_ids if identifier in pays]
        # All postings in a claim must belong to its declared documentary family.
        if issue.type in ('duplicate_accounts', 'period_misclassification'):
            if len(affected_invoices) != 1 or any(
                row.invoice_id != affected_invoices[0].invoice_id or row.payment_id is not None
                or row.currency != affected_invoices[0].currency
                for row in affected_rows
            ):
                errors.append(f'{label}: postings do not belong to the declared invoice')
        elif affected_payments:
            pay = affected_payments[0]
            if any(row.payment_id != pay.payment_id or row.invoice_id not in pay.invoice_refs
                   for row in affected_rows):
                errors.append(f'{label}: postings do not belong to the declared payment')
            if issue.type == 'partial_payment' and (len(affected_rows) != 2 or any(row.currency != pay.currency for row in affected_rows)):
                errors.append(f'{label}: allocation requires the two source-currency postings')
            if issue.type == 'wrong_fx_or_date' and (len(affected_rows) != 4 or len(affected_invoices) != 1
                or affected_invoices[0].invoice_id not in pay.invoice_refs):
                errors.append(f'{label}: FX settlement requires four linked postings and its invoice')
        amount = None
        currency = None
        required = {row.row_id for row in affected_rows}
        if issue.type == 'duplicate_accounts':
            if len(affected_invoices) != 1 or len(affected_rows) != 4:
                errors.append(f'{label}: duplication requires one invoice and four postings')
            else:
                invoice = affected_invoices[0]
                required.add(invoice.doc_id)
                debits = [row for row in affected_rows if row.debit_minor]
                credits = [row for row in affected_rows if row.credit_minor]
                if (len(debits) != 2 or len(credits) != 2
                    or any((row.debit_minor or row.credit_minor) != invoice.total_minor
                           or row.currency != invoice.currency for row in affected_rows)
                    or {row.account for row in debits} != {ACCOUNTS['AR']}
                    or {row.account for row in credits} != {ACCOUNTS['REVENUE']}):
                    errors.append(f'{label}: postings do not demonstrate duplication')
                amount, currency = invoice.total_minor, invoice.currency
        elif issue.type == 'partial_payment':
            if len(affected_payments) != 1:
                errors.append(f'{label}: partial allocation needs one payment')
            else:
                pay = affected_payments[0]
                required.add(pay.doc_id)
                if (sum(bool(row.credit_minor and row.account == ACCOUNTS['AR']) for row in affected_rows) != 1
                    or sum(bool(row.debit_minor and row.account in (ACCOUNTS['CASH'], ACCOUNTS['FX_CLEARING'])) for row in affected_rows) != 1):
                    errors.append(f'{label}: invalid source allocation accounts')
                allocated = sum(row.credit_minor for row in affected_rows
                                if row.account == ACCOUNTS['AR'] and row.currency == pay.currency)
                amount, currency = pay.amount_minor - allocated, pay.currency
                if amount <= 0 or pay.direction != 'receipt':
                    errors.append(f'{label}: no missing receipt allocation')
        elif issue.type == 'wrong_fx_or_date':
            if len(affected_payments) == 1:
                pay = affected_payments[0]
                required.add(pay.doc_id)
                source_amount = sum(row.credit_minor for row in affected_rows
                                    if row.account == ACCOUNTS['AR'] and row.currency == pay.currency)
                actual_base = sum(row.debit_minor for row in affected_rows
                                  if row.account == ACCOUNTS['CASH'] and row.currency == manifest.base_currency)
                key = fx_record_id(pay.timestamp[:10], pay.currency, manifest.base_currency)
                source = [row for row in affected_rows if row.currency == pay.currency]
                base = [row for row in affected_rows if row.currency == manifest.base_currency]
                if (len(source) != 2 or len(base) != 2
                    or {row.account for row in source if row.debit_minor} != {ACCOUNTS['FX_CLEARING']}
                    or {row.account for row in source if row.credit_minor} != {ACCOUNTS['AR']}
                    or {row.account for row in base if row.debit_minor} != {ACCOUNTS['CASH']}
                    or {row.account for row in base if row.credit_minor} != {ACCOUNTS['FX_CLEARING']}):
                    errors.append(f'{label}: invalid FX clearing structure')
            elif len(affected_invoices) == 1:  # Legacy invoice-based E3 artifacts.
                invoice = affected_invoices[0]
                source_amount = invoice.total_minor
                actual_base = sum(row.debit_minor for row in affected_rows)
                key = fx_record_id(invoice.issued_at[:10], invoice.currency, manifest.base_currency)
            else:
                key = None
                source_amount = actual_base = 0
                errors.append(f'{label}: FX issue lacks source document')
            for invoice in affected_invoices:
                required.add(invoice.doc_id)
            if key not in rates:
                errors.append(f'{label}: official FX rate not found')
            else:
                required.add(key)
                amount = abs(actual_base - convert_fx(source_amount, rates[key]))
                currency = manifest.base_currency
                if source_amount <= 0 or actual_base <= 0 or amount <= 0:
                    errors.append(f'{label}: no observable FX discrepancy')
        elif issue.type == 'period_misclassification':
            if len(affected_invoices) != 1 or not affected_rows:
                errors.append(f'{label}: period issue lacks invoice/postings')
            else:
                invoice = affected_invoices[0]
                required.add(invoice.doc_id)
                start, end = datetime.fromisoformat(manifest.period_start), datetime.fromisoformat(manifest.period_end)
                inside_document = start <= datetime.fromisoformat(invoice.issued_at) <= end
                if not any((start <= datetime.fromisoformat(row.timestamp) <= end) != inside_document
                           for row in affected_rows):
                    errors.append(f'{label}: document and postings do not cross reporting boundary')
                if (len(affected_rows) != 2
                    or sum(row.debit_minor for row in affected_rows if row.account == ACCOUNTS['AR']) != invoice.total_minor
                    or sum(row.credit_minor for row in affected_rows if row.account == ACCOUNTS['REVENUE']) != invoice.total_minor):
                    errors.append(f'{label}: invalid recognition amount/accounts')
                amount, currency = invoice.total_minor, invoice.currency
        if amount is not None and (amount != issue.expected_amount_minor or currency != issue.currency):
            errors.append(f'{label}: reproduced amount/currency {amount} {currency} differs from truth')
        for evidence in issue.acceptable_evidence_sets:
            if not required.issubset(evidence):
                errors.append(f'{label}: evidence omits necessary public records')

    # Independently reconcile every unmodified clean posting, including credit notes/refunds.
    for invoice in invoices:
        postings = [row for row in ledger if row.invoice_id == invoice.invoice_id and row.payment_id is None]
        if not any(row.row_id in changed_rows for row in postings):
            debit_account = ACCOUNTS['REVENUE'] if invoice.document_type == 'credit_note' else ACCOUNTS['AR']
            credit_account = ACCOUNTS['AR'] if invoice.document_type == 'credit_note' else ACCOUNTS['REVENUE']
            if (len(postings) != 2 or sum(row.debit_minor for row in postings if row.account == debit_account) != invoice.total_minor
                or sum(row.credit_minor for row in postings if row.account == credit_account) != invoice.total_minor
                or any(row.currency != invoice.currency for row in postings)):
                errors.append(f'Unexplained invoice posting discrepancy: {invoice.invoice_id}')
    for pay in payments:
        postings = [row for row in ledger if row.payment_id == pay.payment_id]
        if not any(row.row_id in changed_rows for row in postings):
            debit_account = ACCOUNTS['AR'] if pay.direction == 'refund' else ACCOUNTS['CASH']
            credit_account = ACCOUNTS['CASH'] if pay.direction == 'refund' else ACCOUNTS['AR']
            if (len(postings) != 2 or sum(row.debit_minor for row in postings if row.account == debit_account) != pay.amount_minor
                or sum(row.credit_minor for row in postings if row.account == credit_account) != pay.amount_minor
                or any(row.currency != pay.currency for row in postings)):
                errors.append(f'Unexplained payment posting discrepancy: {pay.payment_id}')

    changes = index_unique(provenance.changes, 'issue_id', 'provenance')
    if set(changes) != issue_ids:
        errors.append('Truth/provenance issue identifiers disagree')
    for issue in truth.issues:
        change = changes.get(issue.issue_id)
        if change is not None:
            for field in ('type', 'affected_ids', 'expected_amount_minor', 'currency', 'acceptable_evidence_sets'):
                if getattr(change, field) != getattr(issue, field):
                    errors.append(f'Issue {issue.issue_id}: provenance differs on {field}')
            if not change.before_state or not change.after_state:
                errors.append(f'Issue {issue.issue_id}: missing causal snapshots')
    return errors
