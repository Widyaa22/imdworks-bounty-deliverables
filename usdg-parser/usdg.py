"""Exact parser and canonical formatter for a six-decimal USDG token."""

import re

SCALE = 1_000_000
_GRAMMAR = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,6}))?", re.ASCII)


class ParseError(ValueError):
    """Raised when USDG text is outside the accepted grammar."""


def parse_usdg(text: str) -> int:
    """Parse accepted USDG text into integer microunits, without floats."""
    if not isinstance(text, str):
        raise TypeError("USDG text must be str")
    match = _GRAMMAR.fullmatch(text)
    if match is None:
        raise ParseError("expected (0|[1-9][0-9]*)(.[0-9]{1,6})?")
    dot = text.find(".")
    if dot < 0:
        return int(text) * SCALE
    fraction = match.group(1)
    return int(text[:dot]) * SCALE + int(fraction) * (10 ** (6 - len(fraction)))


def format_usdg(microunits: int) -> str:
    """Format non-negative integer microunits as canonical six decimals."""
    if isinstance(microunits, bool) or not isinstance(microunits, int):
        raise TypeError("microunits must be an int")
    if microunits < 0:
        raise ValueError("microunits must be non-negative")
    whole, fraction = divmod(microunits, SCALE)
    return f"{whole}.{fraction:06d}"
