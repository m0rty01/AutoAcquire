# Deploying AutoAcquire AI — Render (frontend + backend) + MongoDB Atlas

Custom domain target: **https://autoacquire.ravijha.co** (root domain `ravijha.co`).

Architecture after deploy:
- **Frontend (React)** → Render Static Site → served at `autoacquire.ravijha.co`
- **Backend (FastAPI)** → Render Web Service → `https://autoacquire-backend.onrender.com`
- **Database** → MongoDB Atlas (free M0 tier is fine to start)

---

## 0. Push code to GitHub
Use the **“Save to GitHub”** button in the Emergent chat input to push this repo to your GitHub account. Everything below assumes the repo is on GitHub.

---

## 1. MongoDB Atlas
1. Create a free account at https://www.mongodb.com/cloud/atlas and create a **free M0 cluster**.
2. **Database Access** → add a database user (username + password). Save the password.
3. **Network Access** → Add IP `0.0.0.0/0` (allow from anywhere — Render IPs are dynamic).
4. **Connect** → **Drivers** → copy the SRV connection string. It looks like:
   `mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   Replace `<user>` and `<password>` with the credentials from step 2. **This is your `MONGO_URL`.**

---

## 2. Deploy on Render (Blueprint)
This repo ships a `render.yaml` blueprint that defines both services.

1. Go to https://dashboard.render.com → **New +** → **Blueprint**.
2. Connect your GitHub repo. Render reads `render.yaml` and shows two services:
   `autoacquire-backend` and `autoacquire-frontend`.
3. Click **Apply**. Render will ask you to fill the secret env vars (`sync: false`).

### Backend env vars to set
| Key | Value |
|-----|-------|
| `MONGO_URL` | your Atlas SRV string from step 1 |
| `CORS_ORIGINS` | `https://autoacquire.ravijha.co,https://autoacquire-frontend.onrender.com` |
| `ADMIN_PASSWORD` | `Admin123!` (or a strong password of your choice) |
| `EMERGENT_LLM_KEY` | from Emergent → Profile → Universal Key |

`DB_NAME`, `ADMIN_EMAIL`, `PYTHON_VERSION` are preset; `JWT_SECRET` is auto-generated.

> **Order of deploy:** let the **backend** finish first so you know its URL.
> Its URL will be `https://autoacquire-backend.onrender.com` (or whatever Render assigns).

### Frontend env var to set
| Key | Value |
|-----|-------|
| `REACT_APP_BACKEND_URL` | the backend URL from above, e.g. `https://autoacquire-backend.onrender.com` (NO trailing slash) |

> ⚠️ `REACT_APP_BACKEND_URL` is baked in at **build time**. If you change it later,
> trigger a **Manual Deploy → Clear build cache & deploy** on the frontend.

4. After both build (5–10 min), open the frontend `.onrender.com` URL and confirm the app loads,
   login works (`admin@autoacquire.ai` / your `ADMIN_PASSWORD`), and the seller chat at
   `/sell/prestige-auto-toronto` responds.

---

## 3. Custom domain: autoacquire.ravijha.co
On the **frontend** service in Render:
1. **Settings → Custom Domains → Add Custom Domain** → enter `autoacquire.ravijha.co`.
2. Render shows a **CNAME target** (like `autoacquire-frontend.onrender.com`).
3. At your DNS provider for `ravijha.co`, add a record:
   - **Type:** CNAME
   - **Name/Host:** `autoacquire`  (the subdomain part only)
   - **Value/Target:** the Render CNAME target from step 2
   - **TTL:** default / automatic
4. Back in Render, click **Verify**. Render auto-issues an SSL certificate.
   Propagation is usually 5–15 min (up to 24h max).

> After the domain is live, make sure `CORS_ORIGINS` on the **backend** includes
> `https://autoacquire.ravijha.co` (it does per step 2). If you edit it, redeploy the backend.

---

## 4. Notes & caveats
- **Seed data:** the backend seeds a demo dealership (`Prestige Auto Toronto`, 24 vehicles, sample leads)
  on first startup. Harmless for a demo; remove the `await seed_demo()` call in `backend/server.py`
  startup if you want a clean production DB.
- **Emergent LLM key:** the AI chat uses your Emergent Universal Key via the `emergentintegrations`
  library. It calls Emergent's LLM proxy over the internet, so it works off-platform as long as the
  key is valid and your Emergent balance has credits. If you'd rather not depend on Emergent off-platform,
  we can swap the AI to a direct Google Gemini API key.
- **Render free/starter cold starts:** on the free tier the backend sleeps after inactivity and the first
  request takes ~30–50s to wake. Use the **Starter** plan (set in `render.yaml`) to avoid this.
- **Google Sign-In (Emergent OAuth):** works with the custom domain because redirect URLs are built
  dynamically from the browser origin. No extra config needed.
