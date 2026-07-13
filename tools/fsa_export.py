#!/usr/bin/env python3
"""Export hotel data from the Росаккредитация hospitality registry.

The script is intentionally self-contained and uses only Python's standard library.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "https://tourism.fsa.gov.ru"
SHOWCASE = "/api/v1/resorts/hotels/showcase"

PARAMS = [
    ("regionIdList", "50"),
    ("categoryIdList", "3"),
    ("categoryIdList", "4"),
    ("categoryIdList", "5"),
    ("statusIdList", "6"),
    ("page", "0"),
    ("limit", "20"),
]


def get_json(path: str, params: list[tuple[str, str]] | None = None) -> Any:
    query = urllib.parse.urlencode(params or [], doseq=True)
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; NewSmart-FSA-Exporter/1.0)",
        },
    )
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}")


def main() -> int:
    out_dir = Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = get_json(SHOWCASE, PARAMS)
    (out_dir / "fsa_showcase_sample.json").write_text(
        json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(sample, ensure_ascii=False)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
