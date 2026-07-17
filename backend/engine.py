"""Deterministic business logic: qualification, lead scoring, inventory matching, availability."""
from datetime import datetime, timedelta, timezone

SCORE_VERSION = "v1"


def _get_field(state: dict, path: str):
    """Read dotted path from lead state {'seller':..,'vehicle':..,'intent':..}."""
    node = state
    for part in path.split("."):
        if isinstance(node, dict):
            node = node.get(part)
        else:
            return None
    return node


def _compare(actual, operator, expected):
    if actual is None:
        return None  # cannot evaluate
    try:
        if operator == "less_than_or_equal":
            return actual <= expected
        if operator == "greater_than_or_equal":
            return actual >= expected
        if operator == "less_than":
            return actual < expected
        if operator == "greater_than":
            return actual > expected
        if operator == "equals":
            return str(actual).lower() == str(expected).lower()
        if operator == "not_equals":
            return str(actual).lower() != str(expected).lower()
        if operator == "in":
            return str(actual).lower() in [str(e).lower() for e in expected]
        if operator == "not_in":
            return str(actual).lower() not in [str(e).lower() for e in expected]
    except Exception:
        return None
    return None


def run_qualification(state: dict, rules: list) -> dict:
    """Evaluate active rules deterministically. Returns status + applied rules."""
    applied = []
    outcome_rank = {"qualified": 0, "partially_qualified": 1,
                    "needs_review": 2, "disqualified": 3, "insufficient_information": 4}
    worst = "qualified"
    total_adjustment = 0
    requires_review = False
    evaluated_any = False

    for rule in sorted(rules, key=lambda r: r.get("priority", 100)):
        if not rule.get("active", True):
            continue
        actual = _get_field(state, rule["field_name"])
        passed = _compare(actual, rule["operator"], rule["comparison_value"])
        if passed is None:
            applied.append({"rule": rule["name"], "result": "skipped_missing_data",
                            "field": rule["field_name"]})
            continue
        evaluated_any = True
        result = rule["success_result"] if passed else rule["failure_result"]
        if not passed:
            total_adjustment += rule.get("score_adjustment", 0)
            if rule.get("review_flag"):
                requires_review = True
        if outcome_rank.get(result, 0) > outcome_rank.get(worst, 0):
            worst = result
        applied.append({"rule": rule["name"], "passed": passed, "result": result,
                        "field": rule["field_name"], "actual": actual,
                        "score_adjustment": rule.get("score_adjustment", 0) if not passed else 0})

    if not evaluated_any:
        status = "insufficient_information"
    elif worst == "disqualified":
        status = "disqualified"
    elif requires_review or worst == "needs_review":
        status = "needs_human_review"
    elif worst == "partially_qualified":
        status = "partially_qualified"
    else:
        status = "qualified"

    return {"qualification_status": status, "applied_rules": applied,
            "requires_human_review": requires_review,
            "rule_adjustment": total_adjustment}


INTENT_STRENGTH = {
    "sell": 20, "trade_in": 20, "upgrade": 18, "buy_another": 16,
    "receive_appraisal": 14, "reduce_payment": 12, "exit_loan": 12,
    "explore_options": 8, "unclear": 4, "not_interested": 0,
}
TIMELINE_URGENCY = {
    "immediately": 15, "within_7_days": 14, "within_30_days": 11,
    "within_90_days": 6, "more_than_90_days": 3, "researching_only": 2, "unknown": 4,
}


def compute_score(state: dict, rule_adjustment: int = 0) -> dict:
    vehicle = state.get("vehicle", {}) or {}
    seller = state.get("seller", {}) or {}
    intent = state.get("intent", {}) or {}

    intent_score = INTENT_STRENGTH.get(intent.get("primary_intent"), 6)
    urgency_score = TIMELINE_URGENCY.get(intent.get("timeline"), 4)

    # vehicle desirability (max 20)
    vehicle_score = 0
    year = vehicle.get("year")
    if isinstance(year, (int, float)):
        vehicle_score += max(0, min(10, (year - 2008) * 0.8))
    mileage = vehicle.get("mileage")
    if isinstance(mileage, (int, float)):
        vehicle_score += 6 if mileage <= 120000 else (3 if mileage <= 200000 else 0)
    cond = (vehicle.get("condition") or "").lower()
    vehicle_score += {"excellent": 4, "good": 3, "fair": 2, "poor": 0, "damaged": 0}.get(cond, 1)
    vehicle_score = min(20, round(vehicle_score))

    # asking price realism (max 15)
    asking = vehicle.get("asking_price")
    price_score = 10 if asking is None else (12 if isinstance(asking, (int, float)) and asking > 0 else 6)
    price_score = min(15, price_score)

    # data completeness (max 10)
    tracked = ["year", "make", "model", "mileage", "condition", "ownership_status"]
    filled = sum(1 for f in tracked if vehicle.get(f) not in (None, "", "unknown"))
    completeness_score = round((filled / len(tracked)) * 10)

    # geographic fit (max 10)
    geographic_score = 8 if seller.get("postal_zip_code") else 4

    # appointment readiness (max 10)
    appointment_score = 0
    if seller.get("phone"):
        appointment_score += 5
    if seller.get("email"):
        appointment_score += 3
    if intent.get("appointment_ready"):
        appointment_score += 2
    appointment_score = min(10, appointment_score)

    # penalties
    penalties = []
    total_penalty = 0
    if (vehicle.get("ownership_status") or "unknown") == "unknown":
        penalties.append({"reason": "Ownership uncertainty", "points": -20}); total_penalty -= 20
    if cond == "damaged":
        penalties.append({"reason": "Severe damage", "points": -20}); total_penalty -= 20
    if (vehicle.get("accident_history") or "").lower() in ("rebuilt_or_salvage", "rebuilt", "salvage"):
        penalties.append({"reason": "Rebuilt or salvage title", "points": -25}); total_penalty -= 25
    if (vehicle.get("lien_status") or "").lower() in ("unresolved", "yes") and not vehicle.get("estimated_loan_balance"):
        penalties.append({"reason": "Unresolved lien", "points": -10}); total_penalty -= 10

    base = (intent_score + urgency_score + vehicle_score + price_score +
            completeness_score + geographic_score + appointment_score)
    total = base + total_penalty + rule_adjustment
    total = max(0, min(100, round(total)))

    band = "hot" if total >= 80 else "warm" if total >= 60 else "nurture" if total >= 40 else "low"
    explanation = (f"Intent {intent_score}/20, urgency {urgency_score}/15, vehicle {vehicle_score}/20, "
                   f"price {price_score}/15, completeness {completeness_score}/10, geo {geographic_score}/10, "
                   f"appointment {appointment_score}/10. Penalties {total_penalty}, rule adj {rule_adjustment}.")

    return {
        "total_score": total, "score_band": band,
        "intent_score": intent_score, "urgency_score": urgency_score,
        "vehicle_score": vehicle_score, "price_score": price_score,
        "completeness_score": completeness_score, "geographic_score": geographic_score,
        "appointment_score": appointment_score, "penalties": penalties,
        "explanation": explanation, "rule_version": SCORE_VERSION,
    }


def match_inventory(preference: dict, inventory: list, limit: int = 3) -> list:
    """Deterministic hard-filter + soft-score ranking. Returns top matches."""
    pref = preference or {}
    results = []
    for v in inventory:
        if v.get("status") != "available":
            continue
        conflicts = []
        # hard filters
        if pref.get("max_price") and v.get("price") and v["price"] > pref["max_price"]:
            continue
        if pref.get("min_price") and v.get("price") and v["price"] < pref["min_price"]:
            continue
        if pref.get("preferred_body_types") and v.get("body_type"):
            if v["body_type"].lower() not in [b.lower() for b in pref["preferred_body_types"]]:
                continue
        if pref.get("minimum_seating") and v.get("seating_capacity"):
            if v["seating_capacity"] < pref["minimum_seating"]:
                continue
        if pref.get("maximum_mileage") and v.get("mileage") and v["mileage"] > pref["maximum_mileage"]:
            continue

        score = 40
        reasons = []
        if pref.get("preferred_makes") and v.get("make"):
            if v["make"].lower() in [m.lower() for m in pref["preferred_makes"]]:
                score += 20; reasons.append(f"Matches preferred make {v['make']}")
        if pref.get("preferred_models") and v.get("model"):
            if v["model"].lower() in [m.lower() for m in pref["preferred_models"]]:
                score += 15; reasons.append(f"Matches preferred model {v['model']}")
        if pref.get("preferred_drivetrains") and v.get("drivetrain"):
            if v["drivetrain"].lower() in [d.lower() for d in pref["preferred_drivetrains"]]:
                score += 12; reasons.append(f"{v['drivetrain']} drivetrain as requested")
        if pref.get("preferred_body_types") and v.get("body_type"):
            reasons.append(f"{v['body_type']} body type")
            score += 8
        if pref.get("max_price") and v.get("price"):
            reasons.append(f"Priced ${v['price']:,} within budget")
            score += 5
        if pref.get("minimum_seating") and v.get("seating_capacity"):
            reasons.append(f"Seats {v['seating_capacity']}")
        score = min(100, score)
        results.append({"inventory_vehicle": v, "match_score": score,
                        "match_reasons": reasons or ["Available and within basic criteria"],
                        "conflicts": conflicts})

    results.sort(key=lambda r: r["match_score"], reverse=True)
    for i, r in enumerate(results[:limit]):
        r["ranking"] = i + 1
    return results[:limit]


DAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def generate_slots(availability_rules: list, booked: list, days_ahead: int = 14, max_slots: int = 12) -> list:
    """Generate future appointment slots from availability config, excluding booked."""
    booked_starts = set(b.get("start_time") for b in booked)
    slots = []
    now = datetime.now(timezone.utc)
    for offset in range(1, days_ahead + 1):
        day = now + timedelta(days=offset)
        dow = DAY_NAMES[day.weekday()]
        for rule in availability_rules:
            if not rule.get("active", True):
                continue
            if rule.get("day_of_week") != dow:
                continue
            try:
                sh, sm = map(int, rule["start_time"].split(":"))
                eh, em = map(int, rule["end_time"].split(":"))
            except Exception:
                continue
            dur = rule.get("duration_minutes", 45)
            buf = rule.get("buffer_minutes", 15)
            cur = day.replace(hour=sh, minute=sm, second=0, microsecond=0)
            end = day.replace(hour=eh, minute=em, second=0, microsecond=0)
            while cur + timedelta(minutes=dur) <= end:
                start_iso = cur.isoformat()
                slot_end = cur + timedelta(minutes=dur)
                if start_iso not in booked_starts:
                    slots.append({
                        "start_time": start_iso, "end_time": slot_end.isoformat(),
                        "appointment_type": rule.get("appointment_type", "in_person_appraisal"),
                        "duration_minutes": dur,
                        "location_id": rule.get("dealership_location_id"),
                    })
                cur = slot_end + timedelta(minutes=buf)
                if len(slots) >= max_slots:
                    return slots
    return slots
