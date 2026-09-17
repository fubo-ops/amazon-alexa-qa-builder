#!/usr/bin/env python3
"""Export two workbooks for every already-collected raw ASIN payload."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path

try:
    from .clean_payload import clean_payload
    from .validate_clean_payload import validate as validate_clean
    from .validate_payload import validate_payload
except ImportError:
    from clean_payload import clean_payload
    from validate_clean_payload import validate as validate_clean
    from validate_payload import validate_payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_payloads", nargs="+")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-clean-questions", default="unlimited")
    parser.add_argument("--node", default="node")
    parser.add_argument("--node-modules")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    outputs: list[str] = []
    env = os.environ.copy()
    if args.node_modules:
        env["NODE_PATH"] = args.node_modules

    with tempfile.TemporaryDirectory(prefix="amazon-alexa-qa-") as temp:
        for raw_path in map(Path, args.raw_payloads):
            raw = json.loads(raw_path.read_text(encoding="utf-8"))
            asin = str(raw.get("asin") or "").upper()
            if asin in seen:
                raise ValueError(f"duplicate ASIN input: {asin}")
            seen.add(asin)
            raw_errors = validate_payload(raw)
            if raw_errors:
                raise ValueError(f"{asin} raw validation failed: {raw_errors[:3]}")
            clean = clean_payload(raw, args.max_clean_questions)
            clean_errors = validate_clean(clean)
            if clean_errors:
                raise ValueError(f"{asin} clean validation failed: {clean_errors[:3]}")
            clean_path = Path(temp) / f"{asin}_clean_payload.json"
            clean_path.write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
            raw_xlsx = output_dir / f"{asin}_QA_Raw.xlsx"
            clean_xlsx = output_dir / f"{asin}_QA_Clean.xlsx"
            subprocess.run([args.node, str(root / "build_workbook.mjs"), str(raw_path), str(raw_xlsx)], check=True, env=env)
            subprocess.run([args.node, str(root / "build_clean_workbook.mjs"), str(clean_path), str(clean_xlsx)], check=True, env=env)
            outputs.extend([str(raw_xlsx), str(clean_xlsx)])
    if len(outputs) != len(seen) * 2 or not all(Path(item).is_file() for item in outputs):
        raise RuntimeError("batch export did not create exactly 2N workbooks")
    print(json.dumps({"asins": sorted(seen), "max_clean_questions": args.max_clean_questions, "outputs": outputs}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
