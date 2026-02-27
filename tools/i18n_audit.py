from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


TURKISH_RE = re.compile(r"[ÇĞİÖŞÜçğıöşü]")
TPL_KEY_RE = re.compile(r"""\{\{\s*t\.get\(\s*["']([^"']+)["']""")
JS_STR_RE = re.compile(r"""(['"`])((:\\.|(!\1).)*)\1""", re.S)


def list_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for base in ("pc", "mobile", "core"):
        d = root / base
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".html", ".js", ".py"}:
                continue
            if "__pycache__" in p.parts:
                continue
            out.append(p)
    return out


def extract_template_keys(text: str) -> set[str]:
    return {m.group(1) for m in TPL_KEY_RE.finditer(text)}


def extract_hardcoded_literals(text: str) -> list[str]:
    values: list[str] = []
    for m in JS_STR_RE.finditer(text):
        val = (m.group(2) or "").strip()
        if not val:
            continue
        if "{{" in val or "{%" in val or "t.get(" in val:
            continue
        if TURKISH_RE.search(val):
            values.append(val)
    return values


def audit(root: Path) -> dict:
    files = list_files(root)
    hardcoded: dict[str, list[str]] = {}
    used_keys: set[str] = set()
    for p in files:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        keys = extract_template_keys(txt)
        if keys:
            used_keys.update(keys)
        vals = sorted(set(extract_hardcoded_literals(txt)))
        if vals:
            hardcoded[str(p.relative_to(root))] = vals

    data_dir = root / "data"
    catalogs: dict[str, dict] = {}
    for lang in ("tr", "en", "es"):
        fp = data_dir / f"{lang}.json"
        if fp.exists():
            catalogs[lang] = json.loads(fp.read_text(encoding="utf-8-sig"))
        else:
            catalogs[lang] = {}

    missing: dict[str, list[str]] = {}
    for lang, catalog in catalogs.items():
        missing[lang] = sorted([k for k in used_keys if k not in catalog])

    return {
        "used_key_count": len(used_keys),
        "hardcoded_file_count": len(hardcoded),
        "hardcoded": hardcoded,
        "missing_keys": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit i18n key usage and hardcoded Turkish strings.")
    parser.add_argument("--root", default=".", help="Project root path")
    parser.add_argument("--out", default="i18n_audit_report.json", help="Output report file")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    report = audit(root)
    out = root / args.out
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"report: {out}")
    print(f"used keys: {report['used_key_count']}")
    print(f"files with hardcoded literals: {report['hardcoded_file_count']}")
    for lang, items in report["missing_keys"].items():
        print(f"missing[{lang}]: {len(items)}")


if __name__ == "__main__":
    main()

