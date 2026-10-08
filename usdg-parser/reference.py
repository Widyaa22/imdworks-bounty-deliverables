"""Independent, deliberately simple reference implementation for tests."""


def reference_parse(text: str) -> int:
    """Parse by character scanning; shares no regex/parser logic with usdg.py."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if not text:
        raise ValueError("empty")

    point = -1
    for index, char in enumerate(text):
        if char == ".":
            if point != -1:
                raise ValueError("multiple points")
            point = index
        elif char < "0" or char > "9":
            raise ValueError("non-ASCII digit")

    whole_text = text if point == -1 else text[:point]
    fraction_text = "" if point == -1 else text[point + 1 :]
    if not whole_text or (len(whole_text) > 1 and whole_text[0] == "0"):
        raise ValueError("invalid whole part")
    if point != -1 and not (1 <= len(fraction_text) <= 6):
        raise ValueError("invalid fraction")

    whole = 0
    for char in whole_text:
        whole = whole * 10 + (ord(char) - ord("0"))
    fraction = 0
    for char in fraction_text:
        fraction = fraction * 10 + (ord(char) - ord("0"))
    return whole * 1_000_000 + fraction * 10 ** (6 - len(fraction_text))
