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

## Marketing homepage / landing (2026-08)
- New `/app/frontend/src/pages/Landing.jsx` is now the root route `/` (was redirect → /login).
- Dark "Swiss" landing per design_guidelines.json: glass sticky nav, asymmetric hero with a floating qualified-lead card, stats ribbon, how-it-works bento grid, 6 feature cards, For-dealerships split (showroom image), footer CTA.
- All CTAs (nav Sign in / Get started, hero, dealers, footer) route to `/login` (existing auth flow). Uses @phosphor-icons/react + font-head/font-mono-plex tokens, tailwindcss-animate entrance.
- Self-tested: renders, fonts loaded, no console errors, nav-signup → /login verified. Frontend-only, no backend change.

## CORS permanent safety net (2026-08)
- After the autonovaia.ca migration, users kept hitting CORS blocks because the Render backend CORS_ORIGINS env var wasn't updated. Added `allow_origin_regex=r"https://([a-z0-9-]+\.)*(autonovaia\.ca|onrender\.com|ravijha\.co)$"` to CORSMiddleware (alongside the env list) so those domains are ALWAYS allowed regardless of the env var; evil origins still blocked (400). Requires a BACKEND redeploy to take effect.
- Also fixed a blocking lint: lead-detail endpoint returns `clean(lead)`.
- Verified iteration_8.json (9/9): CORS preflight for autonovaia.ca/www returns ACAO, evil origin blocked, auth/leads/lead-detail/dashboard regression clean, no _id leak.
- Two fix paths for user: (a) fastest — set backend CORS_ORIGINS env on Render to include https://autonovaia.ca,https://www.autonovaia.ca (works with current deployed code); (b) permanent — Save to GitHub + redeploy BACKEND to ship the regex net.

## Domain migration → autonovaia.ca (2026-08) + CORS
- Site moved from autoacquire.ravijha.co to autonovaia.ca (DNS via Cloudflare → Render).
- Bug: backend "stopped working" = CORS. Deployed Render `CORS_ORIGINS` still listed only old domains, so requests from https://autonovaia.ca were blocked (no Access-Control-Allow-Origin). Code is env-driven and correct.
- FIX (Render dashboard, user action): set backend `CORS_ORIGINS=https://autonovaia.ca,https://www.autonovaia.ca,https://autoacquire-frontend.onrender.com`. Also add both to Google OAuth Authorized JavaScript origins.
- WARNING: never use `*` in prod — with allow_credentials=True browsers reject it. Use explicit origins.
- Verified iteration_6.json (7/7): CORS reflects allowed origins + auth flows OK. Updated render.yaml + DEPLOYMENT.md to new domain.

## Performance fix (2026-06 — slow Leads/Dashboard)
- Root cause: N+1 queries. `GET /api/leads` ran 3 sequential per-lead DB calls (seller/vehicle/appointment) for up to 2000 leads → ~3s on Atlas; dashboard_home enrich had the same pattern.
- Fix: batched into a few `$in` queries (sellers/seller_vehicles/appointments) in both `list_leads` and dashboard `enrich`. Added indexes: sellers.id, seller_vehicles.lead_id, appointments.lead_id, appointments(org,status).
- Result: /api/leads ~12ms locally (was 150 round-trips → 4). Verified iteration_5.json (10/10 backend + frontend renders 50 rows, search/sort/pagination intact).
- Backlog: list_leads still `.to_list(2000)` then filters in Python; move search+pagination fully into the DB query once an org exceeds a few hundred leads.

## Auth: real Google OAuth (2026-06 — replaced Emergent bridge)
- Removed the Emergent-managed Google auth (auth.emergentagent.com redirect + /api/auth/google/session + AuthCallback.jsx). Fully Emergent-free.
- Now uses Google Identity Services (GIS): frontend renders the official Google button (when REACT_APP_GOOGLE_CLIENT_ID set); backend `POST /api/auth/google` verifies the Google ID token via google-auth (`google.oauth2.id_token.verify_oauth2_token`, GOOGLE_CLIENT_ID env) and reuses the email-matched user/org creation + JWT.
- New env vars: backend `GOOGLE_CLIENT_ID`, frontend `REACT_APP_GOOGLE_CLIENT_ID` (same Web OAuth client id). Added to render.yaml + DEPLOYMENT.md. Requires the deploy origins in Google Cloud "Authorized JavaScript origins".
- Verified (iteration_4.json): 6/6 backend regression + full frontend regression pass. Real Google popup not automatable (expected).

## Deployment (2026-06 — self-hosted route chosen by user)
- Target: Render (frontend static site + backend web service) + MongoDB Atlas.
- Custom domain: `autoacquire.ravijha.co` (user owns `ravijha.co`) → CNAME to Render frontend.
- Added `render.yaml` (Blueprint: both services, env vars, SPA rewrite) + `DEPLOYMENT.md` (full guide).
- Verified: backend imports clean, frontend `yarn build` succeeds.
- Backend build must use extra index url for emergentintegrations; startCommand binds `$PORT`.
- Set `CORS_ORIGINS` to the frontend domain(s); `REACT_APP_BACKEND_URL` is build-time on Render.
- Caveats flagged: EMERGENT_LLM_KEY portability off-platform; demo seed runs on startup; Render cold starts on free tier.

## AI provider (2026-06 — migrated to direct Gemini)
- Swapped AI orchestrator from Emergent LLM key (emergentintegrations) to the official `google-genai` SDK using the user's own `GEMINI_API_KEY`. Fully independent of Emergent.
- Model: `gemini-flash-latest` (works on the user's free-tier key). NOTE: `gemini-3.1-pro-preview` has free-tier quota 0 on the user's key (429), so it was switched to `gemini-flash-latest`. Override anytime via `GEMINI_MODEL` env (set to `gemini-3.1-pro-preview` once billing is enabled). Structured JSON via `response_mime_type=application/json`, 2-retry + validate + human-review fallback. Gemini errors now logged (logger `autoacquire.ai`).
- Verified: backend imports/starts clean; key authenticates; chat path fails gracefully to human-review on quota (429). Live AI responses resume when the Google project has quota/billing.

## Onboarding Wizard (2026-06)
- First-login setup flow for dealership admins (shows whenever `org.onboarding_complete !== true`, per user choice b).
- 3 steps: Dealership + primary location details → business hours (days + window → availability rows) → optional starter inventory.
- Backend: `POST /api/onboarding/complete` (updates org + upserts location + creates availability & inventory, marks complete) and `POST /api/onboarding/skip`. Both `dealership_admin` only.
- Frontend `OnboardingWizard.jsx` rendered as overlay in `Layout.jsx`; "Skip for now" available. Verified via curl + UI (steps, submit closes wizard, dashboard reveal).

## Notes
- Emails are SIMULATED (console + `notifications` collection), no real send.
- Demo credentials in `/app/memory/test_credentials.md`.
