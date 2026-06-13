"""Sanitized cookie diagnostics for Gemini Web/API readiness."""
import argparse
import json
from pathlib import Path

from .cookies import diagnose_cookie_header, normalize_cookie_input


def diagnose_cookie_file(path):
    raw = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    cookie, sapisid = normalize_cookie_input(raw)
    diag = diagnose_cookie_header(cookie)
    diag["has_normalized_cookie"] = bool(cookie)
    diag["has_extracted_sapisid"] = bool(sapisid)
    diag["normalized_cookie_length"] = len(cookie)
    return diag


def main():
    parser = argparse.ArgumentParser(description="Diagnose Gemini cookie completeness without printing values.")
    parser.add_argument("cookie_file")
    parser.add_argument("--out")
    args = parser.parse_args()

    report = diagnose_cookie_file(args.cookie_file)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"report_path": args.out, "cookie_count": report["cookie_count"]}, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
