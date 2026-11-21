"""Partner inventory integrations. Real partner adapters stay in PENDING CREDENTIALS until authorized
documentation + credentials are supplied; a clearly-labelled sandbox mode exercises the pipeline with sample data."""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit
from auth import require_roles

integrations_router = APIRouter(prefix="/api", tags=["integrations"])
ADMIN = ("platform_admin", "dealership_admin")
VIEW = ADMIN + ("dealership_manager", "platform_support")


class NotConfigured(Exception):
    pass


class PartnerAdapter:
    key, name, kind = "", "", "inventory"
    required = ["API base URL", "API credentials", "Field documentation", "Data-use authorization"]

    async def fetch(self, integ: dict) -> list:
        raise NotConfigured(f"{self.name}: awaiting partner API/feed documentation and credentials")

    def normalize(self, raw: dict) -> dict:
        raise NotConfigured("Field mapping not defined until partner documentation is received")

    def sample(self) -> list:
        return []


class LeDonDeLAuto(PartnerAdapter):
    key, name = "le_don_de_lauto", "Le Don de L'Auto"

    def sample(self):
        return [{"external_id": f"SAMPLE-LDDA-{i}", "code": f"LD{100 + i}", "vin": f"SAMPLEVIN0000LDDA{i}", "make": mk, "model": md,
                 "year": 2022, "trim": "SE", "km": 30000 + i * 1000, "price": 25000 + i * 1500, "transmission": "automatic",
                 "fuel": "gasoline", "photos": [], "description": "SAMPLE DATA — not real inventory",
                 "state": "sold" if i == 3 else "available", "location": "Sample location"}
                for i, (mk, md) in enumerate([("Toyota", "RAV4"), ("Honda", "CR-V"), ("Mazda", "CX-5"), ("Kia", "Sportage")])]

    def normalize(self, r):
        return {"external_vehicle_id": r["external_id"], "inventory_code": r.get("code"), "vin": r.get("vin"),
                "make": r.get("make"), "model": r.get("model"), "year": r.get("year"), "trim": r.get("trim"),
                "mileage": r.get("km"), "price": r.get("price"), "transmission": r.get("transmission"),
                "fuel_type": r.get("fuel"), "images": r.get("photos") or [], "description": r.get("description"),
                "availability": r.get("state", "available"), "location": r.get("location")}


class HGregoire(PartnerAdapter):
    key, name = "h_gregoire", "H. Grégoire"

    def sample(self):
        return [{"Id": f"SAMPLE-HG-{i}", "StockNo": f"HG-{500 + i}", "Vin": f"SAMPLEVIN00000HG{i}",
                 "Vehicle": {"Make": mk, "Model": md, "Year": 2021, "Trim": "LX"}, "Odometer": 45000 + i * 2000,
                 "SellingPrice": 21000 + i * 1200, "Gearbox": "automatic", "Energy": "hybrid",
                 "Media": [], "Notes": "SAMPLE DATA — not real inventory", "Sold": i == 2, "Branch": "Sample branch"}
                for i, (mk, md) in enumerate([("Hyundai", "Tucson"), ("Ford", "Escape"), ("Subaru", "Forester")])]

    def normalize(self, r):  # deliberately different source shape from Le Don de L'Auto
        v = r.get("Vehicle") or {}
        return {"external_vehicle_id": r["Id"], "inventory_code": r.get("StockNo"), "vin": r.get("Vin"), "make": v.get("Make"),
                "model": v.get("Model"), "year": v.get("Year"), "trim": v.get("Trim"), "mileage": r.get("Odometer"),
                "price": r.get("SellingPrice"), "transmission": r.get("Gearbox"), "fuel_type": r.get("Energy"),
                "images": r.get("Media") or [], "description": r.get("Notes"),
                "availability": "sold" if r.get("Sold") else "available", "location": r.get("Branch")}


class LePrixDuGros(PartnerAdapter):
    key, name, kind = "le_prix_du_gros", "Le Prix du Gros", "code_mapping"
    required = ["Inventory-code cross-reference export", "VIN availability confirmation", "Data-use authorization"]


ADAPTERS = {a.key: a for a in (LeDonDeLAuto(), LePrixDuGros(), HGregoire())}


async def _integration(org_id: str, key: str) -> dict:
    if key not in ADAPTERS:
        raise HTTPException(status_code=404, detail="Unknown partner")
    doc = await db.partner_integrations.find_one({"organization_id": org_id, "partner_key": key})
    if not doc:
        doc = {"id": new_id(), "organization_id": org_id, "partner_key": key, "active": False, "sandbox": False,
               "credentials_received": False, "dealer_group_id": None, "last_sync_at": None, "last_success_at": None,
               "last_stats": {}, "last_errors": [], "created_at": now_iso(), "updated_at": now_iso()}
        await db.partner_integrations.insert_one(dict(doc))
    return clean(doc)


def _status(i: dict) -> str:
    if not i.get("active"):
        return "inactive" if i.get("credentials_received") else "pending_credentials"
    if i.get("sandbox"):
        return "sandbox"
    return "error" if i.get("last_errors") else "active"


async def _upsert_mapping(org_id, source, dg_id, n, internal_id, stats):
    """Mapping identity is (source, dealer group, external id); inventory codes are NOT globally unique."""
    q = {"organization_id": org_id, "source": source, "dealer_group_id": dg_id, "external_vehicle_id": n["external_vehicle_id"]}
    m = await db.external_vehicle_mappings.find_one(q)
    entry = {"at": now_iso(), "inventory_code": n.get("inventory_code"), "vin": n.get("vin"), "internal_vehicle_id": internal_id}
    if not m:
        await db.external_vehicle_mappings.insert_one({"id": new_id(), **q, "inventory_code": n.get("inventory_code"), "vin": n.get("vin"),
            "internal_vehicle_id": internal_id, "status": "active", "history": [entry], "created_at": now_iso(), "updated_at": now_iso()})
    elif m.get("internal_vehicle_id") != internal_id or (m.get("vin") and n.get("vin") and m["vin"] != n["vin"]):
        await db.external_vehicle_mappings.update_one({"id": m["id"]}, {"$set": {"status": "conflict", "proposed": entry, "updated_at": now_iso()}})
        stats["conflicts"] += 1
    elif m.get("inventory_code") != n.get("inventory_code"):
        await db.external_vehicle_mappings.update_one({"id": m["id"]}, {"$set": {"inventory_code": n.get("inventory_code"), "updated_at": now_iso()},
                                                     "$push": {"history": entry}})


async def sync_partner(org_id: str, key: str, actor: str) -> dict:
    integ = await _integration(org_id, key)
    adapter = ADAPTERS[key]
    stats = {"imported": 0, "updated": 0, "sold": 0, "removed": 0, "failed": 0, "unmatched": 0, "conflicts": 0}
    errors = []
    if adapter.kind != "inventory":
        raise HTTPException(status_code=400, detail="This partner provides code mappings, not inventory — add mappings instead")
    if not integ.get("active"):
        raise HTTPException(status_code=400, detail="Activate the integration first")
    try:
        raws = adapter.sample() if integ.get("sandbox") else await adapter.fetch(integ)
    except NotConfigured as e:
        raws, errors = [], [str(e)]
    source = f"partner:{key}" + (":sample" if integ.get("sandbox") else "")
    dg_id = integ.get("dealer_group_id")
    seen = set()
    for idx, raw in enumerate(raws, 1):
        try:
            n = adapter.normalize(raw)
            if not n.get("external_vehicle_id") or not n.get("make"):
                stats["failed"] += 1
                errors.append(f"record {idx}: missing external id or make")
                continue
            code = n.get("inventory_code") or n["external_vehicle_id"]
            stock = f"{key}:{n['external_vehicle_id']}"
            seen.add(stock)
            status = "sold" if n.get("availability") == "sold" else "available"
            doc = {"stock_number": stock, "vin": n.get("vin"), "year": n.get("year"), "make": n.get("make"), "model": n.get("model"),
                   "trim": n.get("trim"), "mileage": n.get("mileage"), "price": n.get("price"), "transmission": n.get("transmission"),
                   "fuel_type": n.get("fuel_type"), "image_url": (n.get("images") or [None])[0], "description": n.get("description"),
                   "location": n.get("location"), "status": status, "external_vehicle_id": n["external_vehicle_id"],
                   "inventory_code": code, "organization_id": org_id, "dealer_group_id": dg_id, "source": source,
                   "is_sample": bool(integ.get("sandbox")), "last_seen_at": now_iso(), "updated_at": now_iso()}
            ex = await db.inventory_vehicles.find_one({"organization_id": org_id, "source": source, "stock_number": stock})
            if not ex and n.get("vin"):
                dup = await db.inventory_vehicles.find_one({"organization_id": org_id, "vin": n["vin"], "source": {"$ne": source}})
                if dup:
                    stats["unmatched"] += 1
                    errors.append(f"{n['external_vehicle_id']}: VIN already present from {dup.get('source')} — flagged for review")
            if ex:
                await db.inventory_vehicles.update_one({"id": ex["id"]}, {"$set": doc})
                vid = ex["id"]
                stats["updated"] += 1
            else:
                vid = new_id()
                await db.inventory_vehicles.insert_one({"id": vid, "date_added": now_iso(), "created_at": now_iso(), **doc})
                stats["imported"] += 1
            stats["sold"] += status == "sold"
            await _upsert_mapping(org_id, key, dg_id, n, vid, stats)
        except Exception as e:
            stats["failed"] += 1
            errors.append(f"record {idx}: {e}")
    if seen:
        res = await db.inventory_vehicles.update_many({"organization_id": org_id, "source": source, "stock_number": {"$nin": list(seen)},
            "status": {"$nin": ["unavailable", "sold"]}}, {"$set": {"status": "unavailable", "updated_at": now_iso()}})
        stats["removed"] = res.modified_count
    ok = not errors or bool(seen)
    upd = {"last_sync_at": now_iso(), "last_stats": stats, "last_errors": errors[:20], "updated_at": now_iso(),
           **({"last_success_at": now_iso()} if ok and seen else {})}
    await db.partner_integrations.update_one({"id": integ["id"]}, {"$set": upd})
    await db.integration_sync_logs.insert_one({"id": new_id(), "organization_id": org_id, "partner_key": key, "actor": actor,
        "sandbox": bool(integ.get("sandbox")), "stats": stats, "errors": errors[:50], "created_at": now_iso()})
    return {"stats": stats, "errors": errors[:20]}


@integrations_router.get("/integrations")
async def list_integrations(user: dict = Depends(require_roles(*VIEW))):
    out = []
    for key, a in ADAPTERS.items():
        i = await _integration(user["organization_id"], key)
        i.update(name=a.name, kind=a.kind, required=a.required, status=_status(i),
                 vehicle_count=await db.inventory_vehicles.count_documents({"organization_id": user["organization_id"], "source": {"$regex": f"^partner:{key}"}, "status": "available"}),
                 open_conflicts=await db.external_vehicle_mappings.count_documents({"organization_id": user["organization_id"], "source": key, "status": "conflict"})
                 + await db.code_mappings.count_documents({"organization_id": user["organization_id"], "status": "conflict"}) * (key in ("le_prix_du_gros", "le_don_de_lauto")))
        out.append(i)
    return out


class IntegrationPatch(BaseModel):
    active: Optional[bool] = None
    sandbox: Optional[bool] = None
    dealer_group_id: Optional[str] = None


@integrations_router.patch("/integrations/{key}")
async def update_integration(key: str, body: IntegrationPatch, user: dict = Depends(require_roles(*ADMIN))):
    i = await _integration(user["organization_id"], key)
    upd = body.model_dump(exclude_unset=True)
    if upd.get("dealer_group_id") and not await db.dealer_groups.find_one({"id": upd["dealer_group_id"], "organization_id": user["organization_id"]}):
        raise HTTPException(status_code=400, detail="Dealer group not found")
    if upd.get("active") and not (upd.get("sandbox", i.get("sandbox")) or i.get("credentials_received")):
        raise HTTPException(status_code=400, detail="Pending credentials — only sandbox (sample data) mode can be activated")
    await db.partner_integrations.update_one({"id": i["id"]}, {"$set": {**upd, "updated_at": now_iso()}})
    await audit(user["organization_id"], "user", user["id"], "partner_integration", i["id"], "updated", None, upd)
    return {"success": True}


@integrations_router.post("/integrations/{key}/sync")
async def manual_sync(key: str, user: dict = Depends(require_roles(*ADMIN))):
    return await sync_partner(user["organization_id"], key, user.get("email"))


@integrations_router.get("/integrations/{key}/logs")
async def sync_logs(key: str, user: dict = Depends(require_roles(*VIEW))):
    return [clean(r) for r in await db.integration_sync_logs.find({"organization_id": user["organization_id"], "partner_key": key}).sort("created_at", -1).to_list(50)]


@integrations_router.get("/integrations/mappings")
async def list_mappings(user: dict = Depends(require_roles(*VIEW)), status: Optional[str] = None):
    q = {"organization_id": user["organization_id"], **({"status": status} if status else {})}
    return {"vehicle_mappings": [clean(m) for m in await db.external_vehicle_mappings.find(q).sort("updated_at", -1).to_list(500)],
            "code_mappings": [clean(m) for m in await db.code_mappings.find(q).sort("updated_at", -1).to_list(500)]}


class CodeMapBody(BaseModel):
    from_dealer_group_id: Optional[str] = None
    ldda_code: str
    lpdg_code: str
    vin: Optional[str] = None


@integrations_router.post("/integrations/code-mappings")
async def add_code_mapping(body: CodeMapBody, user: dict = Depends(require_roles(*ADMIN))):
    """Le Don de L'Auto ↔ Le Prix du Gros code mapping. Never overwrites: conflicting proposals go to manual review."""
    org = user["organization_id"]
    scope = {"organization_id": org, "dealer_group_id": body.from_dealer_group_id}
    veh = await db.external_vehicle_mappings.find_one({"organization_id": org, "source": "le_don_de_lauto",
        **({"vin": body.vin} if body.vin else {"inventory_code": body.ldda_code})})
    entry = {"ldda_code": body.ldda_code, "lpdg_code": body.lpdg_code, "vin": body.vin, "by": user.get("email"), "at": now_iso(),
             "internal_vehicle_id": (veh or {}).get("internal_vehicle_id")}
    existing = await db.code_mappings.find_one({**scope, "$or": [{"ldda_code": body.ldda_code}, {"lpdg_code": body.lpdg_code}]})
    if existing and (existing["ldda_code"], existing["lpdg_code"]) == (body.ldda_code, body.lpdg_code):
        return {"status": "unchanged", "id": existing["id"]}
    if existing:
        await db.code_mappings.update_one({"id": existing["id"]}, {"$set": {"status": "conflict", "proposed": entry, "updated_at": now_iso()}})
        return {"status": "conflict", "id": existing["id"]}
    doc = {"id": new_id(), **scope, "ldda_code": body.ldda_code, "lpdg_code": body.lpdg_code, "vin": body.vin,
           "internal_vehicle_id": entry["internal_vehicle_id"], "match_method": "vin" if body.vin and veh else "code" if veh else "none",
           "status": "active" if veh else "unmatched", "history": [entry], "created_at": now_iso(), "updated_at": now_iso()}
    await db.code_mappings.insert_one(dict(doc))
    return {"status": doc["status"], "id": doc["id"]}


class ResolveBody(BaseModel):
    action: str
    note: Optional[str] = None


@integrations_router.post("/integrations/mappings/{mid}/resolve")
async def resolve_mapping(mid: str, body: ResolveBody, user: dict = Depends(require_roles(*ADMIN))):
    if body.action not in ("accept_proposed", "keep_existing"):
        raise HTTPException(status_code=400, detail="Action must be accept_proposed or keep_existing")
    for coll in (db.external_vehicle_mappings, db.code_mappings):
        m = await coll.find_one({"id": mid, "organization_id": user["organization_id"]})
        if not m:
            continue
        if m.get("status") != "conflict":
            raise HTTPException(status_code=400, detail="Mapping has no open conflict")
        p = m.get("proposed") or {}
        hist = {"at": now_iso(), "by": user.get("email"), "resolution": body.action, "note": body.note, "previous": {k: m.get(k) for k in p}}
        upd = {"status": "active", "proposed": None, "updated_at": now_iso()}
        if body.action == "accept_proposed":
            upd.update({k: v for k, v in p.items() if k not in ("at", "by") and v is not None})
        await coll.update_one({"id": mid}, {"$set": upd, "$push": {"history": hist}})
        await audit(user["organization_id"], "user", user["id"], "mapping", mid, f"conflict_{body.action}")
        return {"success": True}
    raise HTTPException(status_code=404, detail="Mapping not found")
