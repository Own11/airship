"""Stable public identifiers for records without an on-disk ID column."""


def fx_record_id(date: str, source_currency: str, target_currency: str) -> str:
    """Address an FX quote by its unique natural key, independently of row order."""
    return f"{date}:{source_currency}:{target_currency}"
