#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE = "https://tourism.fsa.gov.ru"
SHOWCASE = "/api/v1/resorts/hotels/showcase"
PARAMS = [
    ("regionIdList", "50"),
    ("categoryIdList", "3"),
    ("categoryIdList", "4"),
    ("categoryIdList", "5"),
    ("statusIdList", "6"),
    ("page", "0"),
    ("limit", "1000"),
]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)[\s()\-\d]{9,20}")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def get_json(path: str, params=None) -> Any:
    query = urllib.parse.urlencode(params or [], doseq=True)
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/149 Safari/537.36",
        "Referer": BASE + "/ru/resorts/showcase/hotels",
    })
    error = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            error = exc
            time.sleep(min(30, 2 ** attempt))
    raise RuntimeError(f"GET {url}: {error}")


def walk(value: Any, path: str = ""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from walk(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")
    else:
        yield path, value


def collect_contacts(*payloads: Any):
    emails, phones, sites = set(), set(), set()
    contact_fields = {}
    for payload in payloads:
        for path, value in walk(payload):
            if value is None:
                continue
            s = str(value).strip()
            low = path.lower()
            if any(x in low for x in ("email", "mail")):
                emails.update(EMAIL_RE.findall(s))
                if s: contact_fields[path] = s
            if any(x in low for x in ("phone", "telephone", "tel")):
                phones.update(p.strip(" .,;") for p in PHONE_RE.findall(s))
                if s: contact_fields[path] = s
            if any(x in low for x in ("site", "website", "url", "web")):
                sites.update(URL_RE.findall(s))
                if s.startswith(("www.", "http")): sites.add(s)
                if s: contact_fields[path] = s
            emails.update(EMAIL_RE.findall(s))
            sites.update(URL_RE.findall(s))
        
    return sorted(emails), sorted(phones), sorted(sites), contact_fields


def names(seq):
    return "; ".join(str(x.get("name", "")).strip() for x in (seq or []) if isinstance(x, dict) and x.get("name"))


def main():
    out = Path("data")
    out.mkdir(exist_ok=True)
    showcase = get_json(SHOWCASE, PARAMS)
    items = showcase.get("data", showcase if isinstance(showcase, list) else [])
    enriched = []
    errors = []
    for idx, item in enumerate(items, 1):
        hid = item["id"]
        payloads = {}
        for label, path in {
            "main": f"/api/v1/resorts/hotels/{hid}/main",
            "additional": f"/api/v1/resorts/common/{hid}/additional-info",
            "drawer": f"/api/v1/resorts/hotels/{hid}/drawer",
        }.items():
            try:
                payloads[label] = get_json(path)
            except Exception as exc:
                payloads[label] = None
                errors.append({"id": hid, "endpoint": label, "error": str(exc)})
        emails, phones, sites, fields = collect_contacts(item, *payloads.values())
        enriched.append({
            "list": item,
            "contacts": {"emails": emails, "phones": phones, "sites": sites, "fields": fields},
            "main": payloads["main"],
            "additional": payloads["additional"],
            "drawer": payloads["drawer"],
        })
        print(f"{idx}/{len(items)} {item.get('fullName')} emails={len(emails)} phones={len(phones)} sites={len(sites)}", flush=True)
        time.sleep(0.08)

    (out / "hotels_enriched.json").write_text(json.dumps({"total": len(enriched), "data": enriched}, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "contacts.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "name", "emails", "phones", "sites"])
        for row in enriched:
            item = row["list"]
            c = row["contacts"]
            w.writerow([item.get("id"), item.get("fullName"), "; ".join(c["emails"]), "; ".join(c["phones"]), "; ".join(c["sites"])])
    print(f"DONE total={len(enriched)} errors={len(errors)}")


if __name__ == "__main__":
    main()
