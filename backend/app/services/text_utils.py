import re

_HEBREW_MARKS = re.compile(r"[\u0591-\u05C7]")
_NON_WORD = re.compile(r"[^\w\u05D0-\u05EA]+", re.UNICODE)


def normalize_hebrew(text: str) -> str:
    text = _HEBREW_MARKS.sub("", text or "")
    text = text.replace("־", " ")
    return " ".join(_NON_WORD.sub(" ", text).lower().split())
