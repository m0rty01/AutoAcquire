"""Source-agnostic inventory connectors: normalize any source into the canonical
vehicle schema and ingest it. Supports csv_upload (push), http_feed (pull), and
stubbed scraper/api connectors that plug into the same pipeline."""
import io
import csv
import json
import re
from collections import Counter
from xml.etree import ElementTree as ET

import httpx

from db import db, new_id, now_iso

CANONICAL = ["stock_number", "vin", "year", "make", "model", "trim", "price", "mileage",
             "body_type", "fuel_type", "transmission", "drivetrain", "exterior_colour",
             "seating_capacity", "location", "status", "vehicle_url", "image_url", "options"]
INT_FIELDS = {"year", "mileage", "seating_capacity"}
FLOAT_FIELDS = {"price"}


def _coerce(key, val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    if key in INT_FIELDS:
        try:
            return int(float(re.sub(r"[^0-9.\-]", "", s) or 0))
        except Exception:
            return None
    if key in FLOAT_FIELDS:
        try:
            return float(re.sub(r"[^0-9.\-]", "", s) or 0)
        except Exception:
            return None
    return s


def normalize_row(raw: dict, mapping: dict = None) -> dict:
    """Map an arbitrary source row into the canonical schema. `mapping` maps a
    canonical field name -> the source's column name (optional per field)."""
    mapping = mapping or {}
    low = {str(k or "").strip().lower(): v for k, v in raw.items()}
    out = {}
    for key in CANONICAL:
        src = mapping.get(key, key)
        val = raw.get(src)
        if val is None:
            val = low.get(str(src).lower())
        out[key] = _coerce(key, val)
    out["status"] = (str(out["status"]).strip().lower() if out.get("status") else "available")
    return out


def parse_csv(text: str) -> list:
    return list(csv.DictReader(io.StringIO(text)))


def parse_json(text: str) -> list:
    data = json.loads(text)
    if isinstance(data, dict):
        for k in ("vehicles", "inventory", "items", "data", "results", "listings"):
            if isinstance(data.get(k), list):
                return data[k]
        return [data]
    return data if isinstance(data, list) else []


def parse_xml(text: str) -> list:
    root = ET.fromstring(text)
    known = {"vehicle", "car", "item", "listing", "unit", "inventoryitem", "inventory_item"}
    candidates = [el for el in root.iter() if el.tag.split("}")[-1].lower() in known]
    if not candidates:
        tags = Counter(ch.tag for ch in root.iter() if len(list(ch)) > 0)
        if tags:
            common = tags.most_common(1)[0][0]
            candidates = [el for el in root.iter() if el.tag == common]
    if not candidates:
        candidates = list(root)
    rows = []
    for el in candidates:
        d = dict(el.attrib)
        for child in el:
            d[child.tag.split("}")[-1]] = (child.text or "").strip()
        rows.append(d)
    return rows


def parse_feed(text: str, fmt: str = None) -> list:
    fmt = (fmt or "").lower()
    stripped = text.lstrip()
    if fmt == "json" or (not fmt and stripped[:1] in ("{", "[")):
        return parse_json(text)
    if fmt == "xml" or (not fmt and stripped[:1] == "<"):
        return parse_xml(text)
    return parse_csv(text)


async def fetch_http(url: str, headers: dict = None):
    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as c:
        r = await c.get(url, headers=headers or {})
        r.raise_for_status()
        return r.text, r.headers.get("content-type", "")


async def ingest_rows(org_id, dealer_group_id, source_id, rows, source_type,
                      mapping=None, full=False):
    """Upsert normalized rows into inventory_vehicles. In `full` mode, any vehicle
    for this source not present in the batch is marked unavailable."""
    imported = updated = 0
    errors = []
    seen = set()
    run_at = now_iso()
    for idx, raw in enumerate(rows, start=1):
        try:
            v = normalize_row(raw, mapping)
            key = v.get("stock_number") or v.get("vin")
            if not key or not v.get("make"):
                errors.append({"row": idx, "error": "Missing stock_number/vin or make"})
                continue
            v["stock_number"] = v.get("stock_number") or key
            seen.add(v["stock_number"])
            doc = {**v, "organization_id": org_id, "dealer_group_id": dealer_group_id,
                   "source_id": source_id, "source": source_type,
                   "last_seen_at": run_at, "updated_at": run_at}
            existing = await db.inventory_vehicles.find_one(
                {"organization_id": org_id, "dealer_group_id": dealer_group_id, "stock_number": v["stock_number"]})
            if existing:
                await db.inventory_vehicles.update_one({"id": existing["id"]}, {"$set": doc})
                updated += 1
            else:
                await db.inventory_vehicles.insert_one(
                    {"id": new_id(), "date_added": run_at, "created_at": run_at, **doc})
                imported += 1
        except Exception as e:
            errors.append({"row": idx, "error": str(e)})
    deactivated = 0
    if full and source_id and seen:
        res = await db.inventory_vehicles.update_many(
            {"organization_id": org_id, "source_id": source_id,
             "stock_number": {"$nin": list(seen)}, "status": {"$ne": "unavailable"}},
            {"$set": {"status": "unavailable", "updated_at": run_at}})
        deactivated = res.modified_count
    return {"imported": imported, "updated": updated, "deactivated": deactivated,
            "skipped": len(errors), "errors": errors[:20]}


async def run_source_sync(source: dict) -> dict:
    """Pull + ingest a single source based on its type. Push-based and not-yet-built
    connectors return a non-error status so scheduled runs never crash."""
    stype = source.get("type")
    cfg = source.get("config") or {}
    org_id = source["organization_id"]
    dg = source.get("dealer_group_id")
    sid = source["id"]
    mapping = cfg.get("field_mapping") or {}

    if stype == "http_feed":
        url = cfg.get("url")
        if not url:
            raise ValueError("Feed URL not configured")
        text, ct = await fetch_http(url, cfg.get("headers"))
        fmt = cfg.get("format") or ("json" if "json" in ct else "xml" if "xml" in ct else "csv")
        rows = parse_feed(text, fmt)
        return await ingest_rows(org_id, dg, sid, rows, "feed", mapping, full=True)

    if stype == "csv_upload":
        return {"imported": 0, "updated": 0, "deactivated": 0, "skipped": 0, "errors": [],
                "skipped_reason": "push", "message": "CSV upload is push-based — send files to its push URL."}

    if stype in ("scraper", "api"):
        return {"imported": 0, "updated": 0, "deactivated": 0, "skipped": 0, "errors": [],
                "skipped_reason": "stub",
                "message": f"The {stype} connector framework is ready; a source adapter is not configured yet."}

    raise ValueError(f"Unknown source type: {stype}")
