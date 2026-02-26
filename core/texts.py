import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SUPPORTED = {"tr", "en", "es"}


def language(code: str) -> str:
    return code if code in SUPPORTED else "en"


def texts(code: str) -> dict:
    lang = language(code)
    file = DATA / f"{lang}.json"
    if not file.exists():
        return {}
    with file.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)
