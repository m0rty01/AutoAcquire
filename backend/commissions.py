import io
import csv
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from db import db, new_id, now_iso, clean, audit
from auth import require_roles

commission_router = APIRouter(prefix="/api", tags=["commissions"])
FINANCE = ("platform_admin", "dealership_admin", "dealership_manager", "platform_support")


def _period_key(date_iso: str, period: str) -> str:
    y, m = date_iso[:4], int(date_iso[5:7])
    return f"{y}-Q{(m - 1) // 3 + 1}" if period == "quarterly" else f"{y}-{m:02d}"


def _tier_for(tiers: list, n: int) -> Optional[dict]:
    for t in sorted(tiers, key=lambda t: t["min_sales"]):
        if n >= t["min_sales"] and (t.get("max_sales") is None or n <= t["max_sales"]):
            return t
    return None


def _tier_amount(t: dict, sale_amount) -> float:
    return round(float(t.get("amount_per_sale") or 0) + float(sale_amount or 0) * float(t.get("percent_rate") or 0) / 100.0, 2)


async def compute_commission(dg: dict, sale: dict):
    """Returns (amount, basis, adjustments). Previously generated commissions are never modified;
    retroactive uplifts are emitted as separate, explicit adjustment transactions."""
    dg = dg or {}
    model = dg.get("commission_model", "fixed")
    rate = dg.get("commission_rate", 0) or 0
    amt = sale.get("sale_amount")
    if model == "percent" and amt:
        return round(float(amt) * float(rate) / 100.0, 2), f"{rate}% of {amt}", []
    tiers = dg.get("volume_tiers") or []
    if model != "volume" or not tiers:
        amount = rate or dg.get("referral_amount", 0) or 0
        return float(amount), f"flat {amount}", []
    period = dg.get("volume_period", "monthly")
    method = dg.get("volume_method", "incremental")
    pkey = _period_key(sale.get("sale_date") or now_iso(), period)
    eff = dg.get("effective_date") or ""
    peers = [s for s in await db.sales.find({"dealer_group_id": dg["id"], "status": "verified", "id": {"$ne": sale["id"]}}).to_list(10000)
             if _period_key(s.get("sale_date") or "", period) == pkey and (s.get("verified_at") or "")[:10] >= eff]
    n = len(peers) + 1
    tier = _tier_for(tiers, n)
    if not tier:
        return 0.0, f"volume {pkey}: sale #{n} outside configured tiers", []
    amount = _tier_amount(tier, amt)
    basis = f"volume {method} · {pkey} · sale #{n} → {tier.get('name') or 'tier'}"
    adjustments = []
    if method == "retroactive":
        for s in peers:
            target = _tier_amount(tier, s.get("sale_amount"))
            paid = sum(t["amount"] for t in await db.commission_transactions.find(
                {"sale_id": s["id"], "status": {"$ne": "cancelled"}}).to_list(50))
            if round(target - paid, 2) > 0:
                adjustments.append({"sale_id": s["id"], "referral_id": s.get("referral_id"), "amount": round(target - paid, 2),
                                    "basis": f"retroactive uplift to {tier.get('name') or 'tier'} ({pkey}, {n} sales)"})
    return amount, basis, adjustments


class Tier(BaseModel):
    name: Optional[str] = None
    min_sales: int
    max_sales: Optional[int] = None
    amount_per_sale: float = 0
    percent_rate: float = 0


class AgreementBody(BaseModel):
    commission_model: str
    commission_rate: float = 0
    commission_currency: str = "CAD"
    volume_tiers: List[Tier] = []
    volume_period: str = "monthly"
    volume_method: str = "incremental"
    effective_date: Optional[str] = None


@commission_router.put("/dealer-groups/{dg_id}/commission-agreement")
async def set_agreement(dg_id: str, body: AgreementBody, user: dict = Depends(require_roles("platform_admin", "dealership_admin"))):
    dg = await db.dealer_groups.find_one({"id": dg_id, "organization_id": user["organization_id"]})
    if not dg:
        raise HTTPException(status_code=404, detail="Dealer group not found")
    if body.commission_model not in ("fixed", "percent", "volume"):
        raise HTTPException(status_code=400, detail="Invalid commission model")
    if body.volume_period not in ("monthly", "quarterly") or body.volume_method not in ("incremental", "retroactive"):
        raise HTTPException(status_code=400, detail="Invalid period or calculation method")
    tiers = sorted([t.model_dump() for t in body.volume_tiers], key=lambda t: t["min_sales"])
    if body.commission_model == "volume":
        if not tiers:
            raise HTTPException(status_code=400, detail="Volume model needs at least one tier")
        for i, t in enumerate(tiers):
            if t["min_sales"] < 1 or (t["max_sales"] is not None and t["max_sales"] < t["min_sales"]):
                raise HTTPException(status_code=400, detail=f"Tier {i + 1} has an invalid range")
            if t["amount_per_sale"] < 0 or t["percent_rate"] < 0:
                raise HTTPException(status_code=400, detail="Amounts cannot be negative")
            if i and (tiers[i - 1]["max_sales"] is None or t["min_sales"] <= tiers[i - 1]["max_sales"]):
                raise HTTPException(status_code=400, detail="Tiers overlap")
    version = (dg.get("agreement_version") or 0) + 1
    snapshot = {k: dg.get(k) for k in ("commission_model", "commission_rate", "commission_currency", "volume_tiers",
                                       "volume_period", "volume_method", "effective_date", "agreement_version")}
    await db.commission_agreements.insert_one({"id": new_id(), "organization_id": user["organization_id"], "dealer_group_id": dg_id,
        "superseded_at": now_iso(), "superseded_by": user["id"], "agreement": snapshot})
    upd = {**body.model_dump(), "volume_tiers": tiers, "agreement_version": version,
           "effective_date": body.effective_date or now_iso()[:10], "updated_at": now_iso()}
    await db.dealer_groups.update_one({"id": dg_id}, {"$set": upd})
    await audit(user["organization_id"], "user", user["id"], "commission_agreement", dg_id, "updated", snapshot, upd)
    return clean(await db.dealer_groups.find_one({"id": dg_id}))


@commission_router.get("/dealer-groups/{dg_id}/commission-agreement/history")
async def agreement_history(dg_id: str, user: dict = Depends(require_roles(*FINANCE))):
    rows = await db.commission_agreements.find({"dealer_group_id": dg_id, "organization_id": user["organization_id"]}).sort("superseded_at", -1).to_list(100)
    return [clean(r) for r in rows]


async def _rows(user, date_from, date_to, dealer_group_id, commission_status, sale_status):
    q = {"organization_id": user["organization_id"]}
    if dealer_group_id:
        q["dealer_group_id"] = dealer_group_id
    if sale_status:
        q["status"] = sale_status
    if date_from or date_to:
        q["sale_date"] = {**({"$gte": date_from} if date_from else {}), **({"$lte": date_to + "T23:59:59.999"} if date_to else {})}
    sales = await db.sales.find(q).sort("sale_date", -1).to_list(10000)
    groups = {g["id"]: g for g in await db.dealer_groups.find({"organization_id": user["organization_id"]}).to_list(500)}
    out = []
    for s in sales:
        txns = await db.commission_transactions.find({"sale_id": s["id"]}).sort("created_at", 1).to_list(20) or [None]
        for t in txns:
            if commission_status and (not t or t["status"] != commission_status):
                continue
            out.append({"sale_id": s["id"], "referral_id": s.get("referral_id"), "vehicle": s.get("vehicle_label") or "",
                        "dealership": (groups.get(s.get("dealer_group_id")) or {}).get("name", ""),
                        "sale_date": (s.get("sale_date") or "")[:10], "verification_date": (s.get("verified_at") or "")[:10],
                        "sale_status": s["status"], "sale_amount": s.get("sale_amount"),
                        "commission_model": (t or {}).get("model", ""), "commission_type": (t or {}).get("type", "sale") if t else "",
                        "commission_amount": (t or {}).get("amount"), "commission_status": (t or {}).get("status", ""),
                        "basis": (t or {}).get("basis", ""), "currency": (t or {}).get("currency", "CAD")})
    return out


@commission_router.get("/commissions/ledger")
async def ledger(user: dict = Depends(require_roles(*FINANCE)), date_from: Optional[str] = None, date_to: Optional[str] = None,
                 dealer_group_id: Optional[str] = None, commission_status: Optional[str] = None, sale_status: Optional[str] = None):
    rows = await _rows(user, date_from, date_to, dealer_group_id, commission_status, sale_status)
    return {"rows": rows, "total_commission": round(sum(r["commission_amount"] or 0 for r in rows if r["commission_status"] != "cancelled"), 2),
            "total_sales_amount": round(sum(r["sale_amount"] or 0 for r in rows if r["commission_type"] != "adjustment"), 2)}


COLS = [("sale_id", "Sale ID"), ("referral_id", "Referral ID"), ("vehicle", "Vehicle"), ("dealership", "Dealership"),
        ("sale_date", "Sale date"), ("verification_date", "Verification date"), ("sale_status", "Sale status"),
        ("sale_amount", "Sale amount"), ("commission_model", "Commission model"), ("commission_type", "Type"),
        ("commission_amount", "Commission amount"), ("commission_status", "Commission status"), ("basis", "Basis")]


@commission_router.get("/commissions/export")
async def export(format: str = "csv", user: dict = Depends(require_roles(*FINANCE)), date_from: Optional[str] = None,
                 date_to: Optional[str] = None, dealer_group_id: Optional[str] = None,
                 commission_status: Optional[str] = None, sale_status: Optional[str] = None):
    rows = await _rows(user, date_from, date_to, dealer_group_id, commission_status, sale_status)
    await audit(user["organization_id"], "user", user["id"], "commission_report", None, f"export_{format}", None,
                {"filters": {"date_from": date_from, "date_to": date_to, "dealer_group_id": dealer_group_id}, "rows": len(rows)})
    stamp = now_iso()[:10]
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([c[1] for c in COLS])
        for r in rows:
            w.writerow(["" if r[k] is None else r[k] for k, _ in COLS])
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="autonova-commissions-{stamp}.csv"'})
    if format != "pdf":
        raise HTTPException(status_code=400, detail="Format must be csv or pdf")
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)
    ss = getSampleStyleSheet()
    keys = ["referral_id", "vehicle", "dealership", "sale_date", "verification_date", "sale_amount", "commission_model",
            "commission_amount", "commission_status"]
    head = ["Referral", "Vehicle", "Dealership", "Sale date", "Verified", "Sale $", "Model", "Commission $", "Status"]
    data = [head] + [[(str(r[k])[:8] if k == "referral_id" and r[k] else ("" if r[k] is None else str(r[k]))) for k in keys] for r in rows]
    total = round(sum(r["commission_amount"] or 0 for r in rows if r["commission_status"] != "cancelled"), 2)
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]))
    flt = ", ".join(f"{k}: {v}" for k, v in {"from": date_from, "to": date_to, "dealer group": dealer_group_id,
                                              "commission status": commission_status, "sale status": sale_status}.items() if v) or "none"
    doc.build([Paragraph("AutoNova AI — Commission Report", ss["Title"]),
               Paragraph(f"Generated {stamp} · Filters: {flt} · {len(rows)} rows · Total commission (excl. cancelled): ${total:,.2f}", ss["Normal"]),
               Spacer(1, 12), t])
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="autonova-commissions-{stamp}.pdf"'})
