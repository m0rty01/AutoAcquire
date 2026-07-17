"""Demo seed data: dealership org, users, rules, availability, inventory, leads, conversations, appointments."""
import os
import random
from datetime import datetime, timezone, timedelta
from db import db, new_id, now_iso
from engine import compute_score, run_qualification, match_inventory, SCORE_VERSION

DEMO_SLUG = "prestige-auto-toronto"

DEFAULT_RULES = [
    {"name": "Minimum model year", "category": "acquisition", "field_name": "vehicle.year",
     "operator": "greater_than_or_equal", "comparison_value": 2010, "success_result": "qualified",
     "failure_result": "needs_review", "score_adjustment": -10, "review_flag": True, "priority": 10},
    {"name": "Maximum mileage", "category": "acquisition", "field_name": "vehicle.mileage",
     "operator": "less_than_or_equal", "comparison_value": 220000, "success_result": "qualified",
     "failure_result": "needs_review", "score_adjustment": -15, "review_flag": True, "priority": 20},
    {"name": "Ownership must be clear", "category": "risk", "field_name": "vehicle.ownership_status",
     "operator": "not_equals", "comparison_value": "unknown", "success_result": "qualified",
     "failure_result": "needs_review", "score_adjustment": -20, "review_flag": True, "priority": 30},
    {"name": "Rebuilt or salvage disqualified", "category": "risk", "field_name": "vehicle.accident_history",
     "operator": "not_in", "comparison_value": ["rebuilt_or_salvage", "salvage", "rebuilt"],
     "success_result": "qualified", "failure_result": "disqualified", "score_adjustment": -30,
     "review_flag": False, "priority": 5},
]

DEFAULT_AVAILABILITY = [
    {"appointment_type": "in_person_appraisal", "day_of_week": d, "start_time": "09:00",
     "end_time": "17:00", "duration_minutes": 45, "buffer_minutes": 15, "capacity": 1}
    for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
]

MAKES = ["Toyota", "Honda", "Ford", "Chevrolet", "Mazda", "Hyundai", "Kia", "Subaru", "Nissan", "Jeep"]
MODELS = {"Toyota": ["RAV4", "Corolla", "Highlander", "Camry"], "Honda": ["CR-V", "Civic", "Pilot", "Accord"],
          "Ford": ["Escape", "F-150", "Explorer", "Edge"], "Chevrolet": ["Equinox", "Silverado", "Traverse"],
          "Mazda": ["CX-5", "Mazda3", "CX-9"], "Hyundai": ["Tucson", "Elantra", "Santa Fe"],
          "Kia": ["Sportage", "Sorento", "Forte"], "Subaru": ["Outback", "Forester", "Crosstrek"],
          "Nissan": ["Rogue", "Altima", "Pathfinder"], "Jeep": ["Grand Cherokee", "Wrangler", "Compass"]}
BODY = ["SUV", "Sedan", "Truck", "Hatchback"]
DRIVE = ["AWD", "FWD", "4WD", "RWD"]
IMG = "https://images.unsplash.com/photo-1574023240744-64c47c8c0676?crop=entropy&cs=srgb&fm=jpg&q=85&w=600"
INTENTS = ["sell", "trade_in", "upgrade", "receive_appraisal", "explore_options", "reduce_payment"]
TIMELINES = ["immediately", "within_7_days", "within_30_days", "within_90_days", "researching_only"]
FIRST = ["James", "Maria", "David", "Sarah", "Michael", "Emily", "Robert", "Jessica", "Daniel", "Laura",
         "Kevin", "Amanda", "Brian", "Nicole", "Steven"]
LAST = ["Smith", "Nguyen", "Patel", "Brown", "Tremblay", "Wilson", "Lee", "Martin", "Chen", "Roy",
        "Taylor", "Singh", "Cote", "Wong", "Clark"]


async def seed_demo():
    if await db.organizations.find_one({"slug": DEMO_SLUG}):
        return
    from auth import hash_password
    org_id = new_id()
    await db.organizations.insert_one({
        "id": org_id, "name": "Prestige Auto Toronto", "slug": DEMO_SLUG, "status": "active",
        "country": "CA", "time_zone": "America/Toronto", "plan": "pilot", "onboarding_complete": True,
        "ai_policies": ["Never provide a final vehicle value", "Never guarantee the dealership will purchase the vehicle",
                        "Ask about lien status before appointment booking", "Request a phone number before confirming an appointment",
                        "Escalate all rebuilt-title vehicles"],
        "created_at": now_iso(), "updated_at": now_iso(),
    })
    loc_id = new_id()
    await db.dealership_locations.insert_one({
        "id": loc_id, "organization_id": org_id, "name": "Prestige Auto - Downtown",
        "address_line_1": "1200 Front Street W", "city": "Toronto", "province_state": "ON",
        "postal_zip_code": "M5V 1J5", "country": "CA", "time_zone": "America/Toronto",
        "phone": "+1-416-555-0142", "email": "sales@prestigeauto.example", "service_radius_km": 60,
        "active": True, "created_at": now_iso(), "updated_at": now_iso(),
    })

    users = [
        ("admin@autoacquire.ai", "Admin123!", "dealership_admin", "Alex", "Morgan"),
        ("manager@autoacquire.ai", "Manager123!", "dealership_manager", "Jordan", "Bell"),
        ("rep1@autoacquire.ai", "Rep123!", "dealership_representative", "Sam", "Rivera"),
        ("rep2@autoacquire.ai", "Rep123!", "dealership_representative", "Casey", "Kim"),
        ("platform@autoacquire.ai", "Platform123!", "platform_admin", "Platform", "Owner"),
    ]
    user_ids = {}
    for email, pw, role, fn, ln in users:
        uid = new_id()
        user_ids[role] = user_ids.get(role, uid)
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one({"id": uid, "organization_id": org_id, "first_name": fn,
                "last_name": ln, "email": email, "role": role, "status": "active",
                "auth_provider": "password", "password_hash": hash_password(pw),
                "created_at": now_iso(), "updated_at": now_iso()})

    for r in DEFAULT_RULES:
        await db.qualification_rules.insert_one({"id": new_id(), "organization_id": org_id,
            "active": True, "version": 1, "created_at": now_iso(), "updated_at": now_iso(), **r})
    for a in DEFAULT_AVAILABILITY:
        await db.appointment_availability.insert_one({"id": new_id(), "organization_id": org_id,
            "dealership_location_id": loc_id, "active": True, "created_at": now_iso(),
            "updated_at": now_iso(), **a})

    # inventory (24)
    inv = []
    for i in range(24):
        make = random.choice(MAKES)
        model = random.choice(MODELS[make])
        v = {"id": new_id(), "organization_id": org_id, "dealership_location_id": loc_id,
             "stock_number": f"STK{1000+i}", "vin": f"1{random.randint(10**15, 10**16-1)}",
             "make": make, "model": model, "trim": random.choice(["Base", "LX", "EX", "Sport", "Limited"]),
             "year": random.randint(2018, 2024), "price": random.randint(18000, 48000),
             "mileage": random.randint(10000, 90000), "body_type": random.choice(BODY),
             "fuel_type": random.choice(["gas", "hybrid", "electric"]),
             "transmission": "automatic", "drivetrain": random.choice(DRIVE),
             "exterior_colour": random.choice(["Black", "White", "Silver", "Blue", "Red"]),
             "seating_capacity": random.choice([5, 5, 5, 7, 7]), "location": "Main Lot",
             "status": "available", "source": "seed", "image_url": IMG,
             "date_added": now_iso(), "created_at": now_iso(), "updated_at": now_iso()}
        inv.append(v)
    await db.inventory_vehicles.insert_many([dict(v) for v in inv])

    reps = [u[0] for u in users if u[2] == "dealership_representative"]
    rep_docs = await db.users.find({"email": {"$in": reps}}).to_list(10)
    rep_ids = [r["id"] for r in rep_docs]

    # 16 leads with conversations
    for i in range(16):
        created = datetime.now(timezone.utc) - timedelta(days=random.randint(0, 20), hours=random.randint(0, 20))
        seller_id = new_id()
        fn, ln = random.choice(FIRST), random.choice(LAST)
        has_contact = random.random() > 0.3
        await db.sellers.insert_one({"id": seller_id, "organization_id": org_id, "first_name": fn,
            "last_name": ln, "email": f"{fn.lower()}.{ln.lower()}@example.com" if has_contact else None,
            "phone": f"+1-416-555-{random.randint(1000, 9999)}" if has_contact else None,
            "preferred_contact_method": "email", "postal_zip_code": random.choice(["M5V 1J5", "M4C 1B5", "L4B 3K2"]),
            "city": "Toronto", "province_state": "ON", "country": "CA", "consent_status": "granted",
            "consent_timestamp": created.isoformat(), "marketing_consent": random.random() > 0.5,
            "created_at": created.isoformat(), "updated_at": created.isoformat()})

        lead_id = new_id()
        make = random.choice(MAKES); model = random.choice(MODELS[make])
        forced_review = i < 2  # ensure >=2 human-review leads
        cond = "damaged" if forced_review else random.choice(["excellent", "good", "good", "fair"])
        ownership = "unknown" if (forced_review and i == 1) else random.choice(["owned_outright", "financed", "leased"])
        vehicle = {"id": new_id(), "organization_id": org_id, "lead_id": lead_id, "seller_id": seller_id,
            "vin": None, "year": random.randint(2012, 2023), "make": make, "model": model,
            "trim": random.choice(["LX", "EX", "XLE", "Sport"]), "mileage": random.randint(20000, 210000),
            "mileage_unit": "km", "exterior_colour": random.choice(["Black", "White", "Silver"]),
            "body_type": random.choice(BODY), "fuel_type": "gas", "transmission": "automatic",
            "drivetrain": random.choice(DRIVE), "condition": cond, "ownership_status": ownership,
            "lien_status": "yes" if ownership == "financed" else "no",
            "estimated_loan_balance": random.randint(5000, 20000) if ownership == "financed" else None,
            "asking_price": random.randint(8000, 40000), "accident_history": random.choice(
                ["no_known_accidents", "minor_accident", "no_known_accidents"]),
            "created_at": created.isoformat(), "updated_at": created.isoformat()}
        await db.seller_vehicles.insert_one(dict(vehicle))

        intent = random.choice(INTENTS); timeline = random.choice(TIMELINES)
        pref = None
        if intent in ("trade_in", "upgrade"):
            pref = {"id": new_id(), "organization_id": org_id, "lead_id": lead_id,
                    "max_price": random.choice([30000, 35000, 40000]), "minimum_seating": random.choice([5, 7]),
                    "preferred_body_types": ["SUV"], "preferred_drivetrains": ["AWD"],
                    "created_at": created.isoformat(), "updated_at": created.isoformat()}
            await db.inventory_preferences.insert_one(dict(pref))

        state = {"seller": {"phone": vehicle and (True if has_contact else None), "email": has_contact,
                            "postal_zip_code": "M5V 1J5"},
                 "vehicle": vehicle, "intent": {"primary_intent": intent, "timeline": timeline,
                                                "appointment_ready": has_contact},
                 "preference": pref or {}}
        rules = [{**r, "active": True} for r in DEFAULT_RULES]
        qual = run_qualification(state, rules)
        score = compute_score(state, qual["rule_adjustment"])

        status = random.choice(["new", "ai_qualifying", "qualified", "contacted"])
        if forced_review:
            status = "needs_review"
        appt_booked = i >= 13  # 3 booked appointments
        if appt_booked:
            status = "appointment_booked"

        await db.leads.insert_one({"id": lead_id, "organization_id": org_id, "dealership_location_id": loc_id,
            "seller_id": seller_id, "assigned_user_id": random.choice(rep_ids + [None]),
            "source": "web_conversation", "status": status,
            "qualification_status": qual["qualification_status"], "conversation_mode": "ai_active",
            "primary_intent": intent, "intent_confidence": round(random.uniform(0.8, 0.98), 2),
            "timeline": timeline, "appointment_ready": has_contact, "score": score["total_score"],
            "score_band": score["score_band"], "score_version": SCORE_VERSION,
            "requires_human_review": qual["requires_human_review"] or forced_review,
            "recommended_next_action": "offer_appointment" if has_contact else "request_contact_information",
            "is_test": False, "last_activity_at": created.isoformat(),
            "created_at": created.isoformat(), "updated_at": created.isoformat()})
        await db.lead_scores.insert_one({"id": new_id(), "organization_id": org_id, "lead_id": lead_id,
            **score, "applied_rules": qual["applied_rules"], "created_at": created.isoformat()})

        conv_id = new_id()
        completed_conv = i < 5  # >=5 completed conversations
        await db.conversations.insert_one({"id": conv_id, "organization_id": org_id, "lead_id": lead_id,
            "channel": "web", "status": "closed" if completed_conv else "active",
            "current_stage": "appointment_confirmed" if appt_booked else ("closed" if completed_conv else "vehicle_condition"),
            "rolling_summary": f"Seller {fn} owns a {vehicle['year']} {make} {model}, ~{vehicle['mileage']} km. "
                               f"Intent: {intent}. Timeline: {timeline}.",
            "ai_active": True, "started_at": created.isoformat(),
            "created_at": created.isoformat(), "updated_at": created.isoformat()})

        sample = [
            ("ai", "Hi, I'm Prestige Auto's virtual vehicle assistant (an AI). Are you looking to sell, trade in, or explore your options?"),
            ("seller", f"I have a {vehicle['year']} {make} {model} and I'm thinking about {intent.replace('_', ' ')}."),
            ("ai", f"Great. About how many kilometres are on your {model}?"),
            ("seller", f"Around {vehicle['mileage']:,}."),
            ("ai", "Thanks. Is it fully paid off or is there still a loan?"),
            ("seller", "Still financing it." if vehicle["lien_status"] == "yes" else "Paid off."),
        ]
        t = created
        for stype, content in sample:
            t += timedelta(minutes=random.randint(1, 4))
            await db.messages.insert_one({"id": new_id(), "organization_id": org_id, "conversation_id": conv_id,
                "sender_type": stype, "content": content, "delivery_status": "delivered",
                "model_provider": "gemini" if stype == "ai" else None, "created_at": t.isoformat()})

        if pref:
            inv_docs = await db.inventory_vehicles.find({"organization_id": org_id, "status": "available"}).to_list(1000)
            matches = match_inventory(pref, inv_docs)
            for m in matches:
                await db.inventory_matches.insert_one({"id": new_id(), "organization_id": org_id, "lead_id": lead_id,
                    "inventory_vehicle_id": m["inventory_vehicle"]["id"], "match_score": m["match_score"],
                    "ranking": m["ranking"], "match_reasons": m["match_reasons"], "conflicts": m["conflicts"],
                    "generated_at": now_iso()})

        if appt_booked:
            start = datetime.now(timezone.utc) + timedelta(days=random.randint(1, 6), hours=random.randint(9, 15))
            start = start.replace(minute=0, second=0, microsecond=0)
            await db.appointments.insert_one({"id": new_id(), "organization_id": org_id,
                "dealership_location_id": loc_id, "lead_id": lead_id, "seller_id": seller_id,
                "assigned_user_id": random.choice(rep_ids), "appointment_type": "in_person_appraisal",
                "start_time": start.isoformat(), "end_time": (start + timedelta(minutes=45)).isoformat(),
                "time_zone": "America/Toronto", "status": "confirmed", "booking_source": "ai_conversation",
                "notes": "", "confirmation_sent_at": now_iso(), "created_at": created.isoformat(),
                "updated_at": now_iso()})

    print("[SEED] Demo dealership 'Prestige Auto Toronto' created.")
