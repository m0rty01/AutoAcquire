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

## Inventory Data Feed / DMS ingestion (2026-06-19)
- Client requirement: dealership's DMS/inventory provider wants to push an inventory data export; asked for SFTP folder + required file format.
- Delivered (per user choice): (a) formal spec doc + (b) in-app secure HTTPS ingestion. SFTP kept as client's own infra (guidance only).
- Backend (`server.py`):
  - Refactored CSV import into shared `_run_csv_import(org_id, content, source)`; `/inventory/import` now uses it.
  - `GET /api/inventory/feed-config` (admin/manager) → masked token, absolute `push_url`, `X-Feed-Token` header name, recent feed imports.
  - `POST /api/inventory/feed-config/regenerate` (admin) → rotates key.
  - `POST /api/inventory/feed?token=...` OR header `X-Feed-Token` → token-authenticated CSV ingest (no JWT), source="feed". Bad token → 403.
  - Token stored on `organizations.inventory_feed_token` (secrets.token_urlsafe(24)).
  - New env `PUBLIC_BASE_URL` in backend/.env (preview value set). **On Render set PUBLIC_BASE_URL to the production API domain** so the push URL shown to providers is correct.
- Frontend (`Inventory.jsx`): "Data feed" button → panel with copyable push URL, curl example, regenerate key, recent syncs. Testids: data-feed-btn, feed-config-panel, feed-push-url, copy-feed-url-btn, regen-feed-btn, feed-import-row.
- Verified: curl (feed-config, push CSV imports 1, bad token 403) + UI screenshot (panel renders, pushed vehicle FEED001 appears in list).
- Docs generated in `/app/frontend/public/`: `AutoNova_AI_Project_Scope_Proposal.docx`, `AutoNova_AI_Inventory_Data_Feed_Specification.docx` (both downloadable via public URL).

## Feed enhancements (2026-06-19)
- **Sold Auto-Cleanup**: feed endpoint accepts `mode=full`. Full-snapshot uploads mark feed-sourced vehicles missing from the file as `status=unavailable` (incremental never removes). feed-config now returns `full_push_url`. Verified via curl (deactivated count) + UI.
- **Feed Alerts (in-app only)**: failed syncs (missing required cols → records failed import + `notify` template `feed_sync_failed`, HTTP 400) and skipped rows (`notify` `feed_sync_skipped`) recorded to `notifications`. Inventory page shows an amber warning banner (testid `feed-warning-banner`) when the latest feed import failed/skipped; "Review" opens the panel.
- Field-mapping screen: SKIPPED per user (defaults assumed) — canonical column names used as-is.
- inventory_imports docs now carry `status` (completed/failed), `mode`, `deactivated`. Recent syncs row shows new/updated/hidden/skipped/failed + `full` tag.

## Source-agnostic Inventory Layer + Referrals (Phase 1) (2026-10-01)
Client vision: AutoNova = operator connecting MANY dealer groups; inventory is INTERNAL-ONLY (never shown publicly); AI matches qualified buyers to vehicles across groups → referrals w/ per-group commission (e.g. Le Prix du Gros $200 via Mon Coéquipier). Source-agnostic so a scraper can be swapped for a feed/API later with no rebuild.
- **New collections**: `dealer_groups` (name, website, referral_amount, referral_program, locations, status, is_default), `inventory_sources` (dealer_group_id, type csv_upload|http_feed|scraper|api, config, schedule, enabled, feed_token, last_run_at, last_status, last_stats), `referrals` (lead→dealer_group→vehicle, amount, status pipeline identified→sent→accepted→converted→paid→lost, external_reference=Mon Coéquipier, status_history).
- `inventory_vehicles` extended: `dealer_group_id`, `source_id`, `last_seen_at`. Startup migration `_migrate_dealer_groups()` creates a default "House Inventory" group per org and backfills existing vehicles.
- **connectors.py**: normalize_row (canonical schema + optional field_mapping), parse_csv/json/xml, fetch_http, ingest_rows (upsert by dealer_group+stock, full-snapshot cleanup), run_source_sync (http_feed pulls+ingests full; csv_upload push-based; scraper/api return non-error stub).
- **Endpoints**: /api/dealer-groups CRUD; /api/inventory-sources CRUD + POST /{id}/run; /api/referrals GET + PATCH /{id}; POST /api/cron/sync-sources (Bearer WEBHOOK_CRON_SECRET, backgrounds work via asyncio). Feed endpoint now resolves per-source feed_token (→its group) then legacy org token (→default group). csv_upload sources expose their own push_url/full_push_url.
- **AI matching**: `_run_match` searches ALL groups, stamps dealer_group_id on matches, and `_upsert_referral` auto-creates a referral when a qualified/partially_qualified lead has a top match (amount from group). Public seller chat appends a one-line teaser naming the matched vehicle + dealer group (once per lead, `match_teased`).
- **Frontend**: Partners.jsx (dealer groups + expandable sources, add/edit/delete, per-source push URLs + Run now), Referrals.jsx (stat cards + status dropdown + Mon Coéquipier ref). Nav: Partners, Referrals. Routes /app/partners, /app/referrals.
- **Scheduling**: `.emergent/crons.yml` → sync-inventory every 6h (`0 */6 * * *`) hits /api/cron/sync-sources. New env `WEBHOOK_CRON_SECRET` in backend/.env.
- **Scraper/API**: framework stubbed (returns "framework ready" message) — Phase 2 will add the leprixdugros scraper adapter.
- Tested: iteration_9.json — backend 100% (11/11), frontend 100% core flows, no issues.

