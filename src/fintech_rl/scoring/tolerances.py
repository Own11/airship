from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN, ROUND_FLOOR, ROUND_CEILING
from typing import Dict, Tuple


def get_decimal_rounding_mode(rule: str):
    if rule == "ROUND_HALF_EVEN":
        return ROUND_HALF_EVEN
    elif rule == "ROUND_FLOOR":
        return ROUND_FLOOR
    elif rule == "ROUND_CEILING":
        return ROUND_CEILING
    return ROUND_HALF_UP


def convert_fx(amount_minor: int, rate: Decimal, rounding_mode: str = "ROUND_HALF_UP") -> int:
    """Converts minor units using exact Decimal multiplication and rounding."""
    val = Decimal(amount_minor) * rate
    rm = get_decimal_rounding_mode(rounding_mode)
    return int(val.to_integral_value(rounding=rm))


def is_amount_within_tolerance(
    claimed_minor: int,
    expected_minor: int,
    tolerance_minor: int = 0
) -> bool:
    """Checks if claimed_minor is within absolute tolerance of expected_minor."""
    return abs(claimed_minor - expected_minor) <= tolerance_minor
