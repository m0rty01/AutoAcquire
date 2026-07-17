# AutoAcquire AI — PRD & Build Log

## Original Problem
AI-first SaaS that helps auto dealerships qualify private vehicle sellers via an AI chat and convert them into appraisal/trade-in appointments. Multi-tenant, deterministic business logic, human-in-the-loop.

## Architecture (as built)
- **Stack:** React (CRA + Tailwind + shadcn + Phosphor icons) · FastAPI (modular: db, auth, engine, ai_engine, seed, server) · MongoDB (UUID string ids, ISO datetimes).
- **AI:** Gemini 3.1 Pro (`gemini-3.1-pro-preview`) via emergentintegrations Universal Key. Orchestrator returns strict structured JSON (extraction + intent + nextAction), validated + 1 retry + safe fallback → human review. AI never writes DB/calendar directly; deterministic services do.
- **Auth:** JWT email/password, Bearer token in `Authorization` header (localStorage `aa_token`). RBAC roles: dealership_admin / manager / representative / platform_admin. Tenant isolation via `organization_id` on every query.
- **Deterministic engine:** qualification rules, 0-100 weighted lead scoring (bands hot/warm/nurture/low), inventory matching (hard filters + soft ranking, top 3), availability slot generation with double-book prevention.

## User Personas
Private seller · Dealership admin · Manager · Representative · Platform admin.

## Implemented (2026-06-17)
- Multi-tenant orgs + JWT auth + RBAC + tenant isolation
- Public seller AI conversation page (`/sell/{slug}`) — mobile-first, glass header, typing indicator, streamed-in messages, slot picker, booking confirmation, localStorage persistence
- AI orchestrator: seller/vehicle extraction, intent + timeline detection, conversation stages, rolling summary, structured extraction stored to `extracted_fields`
- Deterministic qualification + lead scoring (stable, auditable) + inventory matching
- Inventory CRUD + CSV import (template, validation, error rows, upsert by stock #)
- Appointment availability + booking + conflict prevention + statuses (complete/cancel/no-show)
- Dealer dashboard (hot/review/new panels, today's appts), Leads list (filters/search/sort), Lead detail (transcript, human takeover + manual messaging + resume AI, vehicle correction w/ recalculation, score breakdown, inventory matches, notes, activity)
- Analytics (metrics + score-band donut + intent bar), Settings (profile, users/invite, qualification rules toggle, availability, AI policies, audit log), Platform admin (org list + failed workflows)
- Audit events, domain events (outbox-style), simulated notifications (logged + stored)
- Seed demo: Prestige Auto Toronto, 5 users, rules, availability, 24 inventory, 16 leads, conversations, 3 appointments, 2 review leads

## Testing
Backend 27/27 pytest pass; Frontend 7/7 flows pass (incl. live Gemini chat). No open issues.

## Backlog (P1/P2, not yet built)
- Emergent Google social login (user asked for both; JWT done, Google pending)
- Financing estimate module (feature-flagged), remote appraisal
- Multiple locations, server-side pagination UI controls, CSV analytics export
- Real email (Resend) instead of simulated
- Rolling-summary auto-regeneration via AI, confidence-based field confirmation UI

## Notes
- Emails are SIMULATED (console + `notifications` collection), no real send.
- Demo credentials in `/app/memory/test_credentials.md`.
