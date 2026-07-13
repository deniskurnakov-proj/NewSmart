#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

BASE = "https://tourism.fsa.gov.ru"
SHOWCASE = "/api/v1/resorts/hotels/showcase"
PARAMS = [("regionIdList", "50"), ("categoryIdList", "3"), ("categoryIdList", "4"), ("categoryIdList", "5"), ("statusIdList", "6"), ("page", "0"), ("limit", "1000")]
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+7|8)[\s()\-\d]{9,20}")
URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)


def get_json(path: str, params=None) -> Any:
    query = urllib.parse.urlencode(params or [], doseq=True)
    url = f"{BASE}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"Accept": "application/json, text/plain, */*", "User-Agent": "Mozilla/5.0 Chrome/149 Safari/537.36", "Referer": BASE + "/ru/resorts/showcase/hotels"})
    error = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:
            error = exc
            time.sleep(min(12, 2 ** attempt))
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
    fields = {}
    for payload in payloads:
        if payload is None:
            continue
        for path, value in walk(payload):
            if value is None:
                continue
            s = str(value).strip()
            low = path.lower()
            emails.update(EMAIL_RE.findall(s))
            sites.update(URL_RE.findall(s))
            if any(x in low for x in ("phone", "telephone", "tel")):
                phones.update(p.strip(" .,;") for p in PHONE_RE.findall(s))
                if s: fields[path] = s
            if any(x in low for x in ("email", "mail", "site", "website", "url", "web")) and s:
                fields[path] = s
                if s.startswith("www."): sites.add("https://" + s)
    return sorted(emails), sorted(phones), sorted(sites), fields


def enrich(item):
    hid = item["id"]
    payloads, errs = {}, []
    for label, path in {"main": f"/api/v1/resorts/hotels/{hid}/main", "additional": f"/api/v1/resorts/common/{hid}/additional-info", "drawer": f"/api/v1/resorts/hotels/{hid}/drawer"}.items():
        try:
            payloads[label] = get_json(path)
        except Exception as exc:
            payloads[label] = None
            errs.append({"id": hid, "endpoint": label, "error": str(exc)})
    emails, phones, sites, fields = collect_contacts(item, *payloads.values())
    return {"list": item, "contacts": {"emails": emails, "phones": phones, "sites": sites, "fields": fields}, **payloads}, errs


def main():
    out = Path("data"); out.mkdir(exist_ok=True)
    showcase = get_json(SHOWCASE, PARAMS)
    items = showcase.get("data", showcase if isinstance(showcase, list) else [])
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {pool.submit(enrich, item): item for item in items}
        for i, fut in enumerate(as_completed(future_map), 1):
            item = future_map[fut]
            try:
                row, errs = fut.result(); results.append(row); errors.extend(errs)
                c = row["contacts"]
                print(f"{i}/{len(items)} {item.get('fullName')} e={len(c['emails'])} p={len(c['phones'])} s={len(c['sites'])}", flush=True)
            except Exception as exc:
                errors.append({"id": item.get("id"), "endpoint": "all", "error": str(exc)})
    order = {x["id"]: i for i, x in enumerate(items)}
    results.sort(key=lambda r: order.get(r["list"]["id"], 999999))
    (out / "hotels_enriched.json").write_text(json.dumps({"total": len(results), "data": results}, ensure_ascii=False), encoding="utf-8")
    (out / "errors.json").write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    with (out / "contacts.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["id", "name", "emails", "phones", "sites"])
        for row in results:
            c = row["contacts"]; w.writerow([row["list"].get("id"), row["list"].get("fullName"), "; ".join(c["emails"]), "; ".join(c["phones"]), "; ".join(c["sites"])])
    print(f"DONE total={len(results)} errors={len(errors)}")


if __name__ == "__main__":
    main()
