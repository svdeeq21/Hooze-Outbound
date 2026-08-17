# RAILWAY_DEPLOYMENT.md — Everything in one Railway project

This is the guide to use if you're already hosting n8n on Railway (as
opposed to `DEPLOYMENT.md`, which is written for a single VPS running both
n8n and Python together). It keeps everything inside your existing Railway
project — no separate server, no Oracle Cloud, no VPS.

## Why this looks different from DEPLOYMENT.md

The original design had n8n directly run Python commands on the same
machine (`Execute Command` nodes shelling out to `python3 -m python.X.Y`).
Railway doesn't work that way — every Railway service is its own isolated
container, so n8n's container can't reach into a Python container and run
a command in it.

The fix: run Python as **its own Railway service**, in the **same Railway
project** as n8n, and let n8n talk to it over HTTP instead of shelling out
to it. Every `n8n/WF-*.json` workflow already reflects this — the nodes
that used to run Python locally now make an HTTP call to
`$env.PYTHON_API_URL` instead. Nothing about what each workflow *does*
changed, only *how* it reaches Python.

```
Your Railway project
┌─────────────────────────────────────────────────────────┐
│                                                            │
│   ┌────────────────┐   private network    ┌─────────────┐│
│   │  n8n service     │ ───────────────────▶│ python-api   ││
│   │  (already exists)│  http://python-api.  │  service     ││
│   │                  │  railway.internal    │  (new)       ││
│   └────────┬─────────┘                     └──────┬──────┘│
│            │                                        │       │
└────────────┼────────────────────────────────────────┼───────┘
             │ public webhooks                         │
             ▼                                         ▼
      dashboard/index.html                    Supabase (cloud, outside
      (anywhere)                               Railway) + Gemini/Groq
```

Key point: **`python-api` never needs a public URL.** It only needs to be
reachable *from n8n*, and Railway gives every service in a project a free
private address automatically — nothing about the Python service is ever
exposed to the internet. n8n stays the only public entry point, same as
the original design intended.

## Step 1 — Add the Python service to your Railway project

1. Open your existing Railway project (the one with n8n in it).
2. Click **+ New** → **GitHub Repo** (or **Empty Service** if you'll deploy
   from a local folder / Railway CLI instead) → select this repo
   (`hooze-outbound`).
3. Railway will try to auto-detect how to run it. This repo has a
   `Procfile` at the root (`web: uvicorn python.api:app --host 0.0.0.0
   --port $PORT`) — Railway's Nixpacks builder picks this up
   automatically for Python projects, so in most cases you don't need to
   configure anything else. If it doesn't auto-detect, go to the service's
   **Settings → Deploy** and set the **Start Command** manually to:
   ```
   uvicorn python.api:app --host 0.0.0.0 --port $PORT
   ```
4. Rename this service to `python-api` (Settings → General → Service Name)
   — the private-network address n8n calls is built from this name, so
   naming it something else means changing `PYTHON_API_URL` in step 3
   below to match.

## Step 2 — Set the Python service's environment variables

On the `python-api` service, go to **Variables** and add:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key-here
GROQ_API_KEY=your-groq-key-here
PYTHON_API_SECRET=pick-a-long-random-string-here
```

`PYTHON_API_SECRET` is a shared secret only n8n and this service know —
every request to `python-api` must include it in an `X-Internal-Secret`
header, or it's rejected with a 401. This matters even though the service
is private-network-only, as a second layer of protection
(`docs/14-security-spec.md` §3's webhook-auth requirement, applied here
too). Generate one with e.g. `openssl rand -hex 32` on any machine, or any
long random string works.

**Do NOT enable public networking for this service** (Settings →
Networking → the "Generate Domain" option) — leave it off. It should only
ever be reachable from inside your Railway project.

## Step 3 — Set two new variables on your n8n service

On your **existing n8n service** (not the new one), go to **Variables**
and add:

```
PYTHON_API_URL=http://python-api.railway.internal:8000
PYTHON_API_SECRET=pick-a-long-random-string-here    (same value as step 2)
```

The hostname `python-api.railway.internal` is Railway's automatic private
address for a service named `python-api` — if you named your service
something else in Step 1, change `python-api` here to match. Port `8000`
is uvicorn's default; Railway's `$PORT` variable inside the python-api
service picks the actual port automatically, but Railway's private
networking maps to whatever `$PORT` resolves to — if you get a connection
error later, check the python-api service's logs for the port it actually
bound to and adjust this URL.

## Step 4 — Deploy and check the health endpoint

Once `python-api` finishes deploying, confirm it's alive. From a Railway
shell on either service (Settings → the "..." menu → "Open Shell", or via
`railway run` locally with the Railway CLI), run:

```bash
curl http://python-api.railway.internal:8000/health
```

You should get back `{"status":"ok"}`. If this fails, check the
`python-api` service's deploy logs — the most common issue is a missing
dependency (`pip install -r python/requirements.txt` not having run,
which Railway's Nixpacks builder should do automatically by detecting
`python/requirements.txt` — if it doesn't, add a `nixpacks.toml` or check
the build logs for what it actually installed).

## Step 5 — Database and Sheets — unchanged

Parts 1, 2, 7, and 8 from `DEPLOYMENT.md` (Supabase setup, AI keys, Google
Sheet templates, and the dashboard) are identical regardless of where n8n
and Python run — follow those sections as written. The only thing that's
different is *this* document's Steps 1-4 above, replacing DEPLOYMENT.md's
Parts 3-6 (the "get a VPS, install Docker/n8n/Python by hand" parts) —
skip those entirely if you're following this guide instead.

## Step 6 — Import the workflows

Same as `DEPLOYMENT.md` Part 6, with one difference: you do **not** need
to check any Execute Command node's working directory (there are none
anymore) — every processing step is now an **HTTP Request** node that
reads `$env.PYTHON_API_URL` automatically, so as long as Step 3 above is
set correctly, every workflow just works after import. Still double-check:

1. Every Supabase-typed node has your Supabase credential attached (this
   didn't change — WF-01, WF-15, and the "get rows to process" nodes in
   every workflow still talk to Supabase directly from n8n).
2. Activate WF-02 through WF-15 once you've confirmed Step 4's health
   check passes.

## Step 7 — Test end-to-end

Follow `DEPLOYMENT.md` Part 9 exactly (add one test lead, manually run
WF-01 through WF-06 in order, confirm it shows up in the dashboard). The
only difference under the hood: each "Run X" step is now an HTTP call to
`python-api` instead of a shell command — if a step fails, check the
`python-api` service's Railway logs (not n8n's) for the actual Python
error, since that's where the code is actually executing now.

## Troubleshooting specific to this setup

- **"Connection refused" / "ECONNREFUSED" from the HTTP Request node** →
  `PYTHON_API_URL` is wrong, or `python-api` isn't actually running.
  Double check the service name matches, and that the service shows
  "Active" (not crashed) in the Railway dashboard.
- **401 "Missing or invalid X-Internal-Secret header"** → `PYTHON_API_SECRET`
  doesn't match between the two services — copy-paste it, don't retype it.
- **Everything times out** → Railway's private networking sometimes takes
  a minute to become reachable right after a service redeploys — wait a
  minute and retry before assuming something's misconfigured.
- **You want to hit `python-api` directly to debug something** → use
  Railway's CLI (`railway run curl http://python-api.railway.internal:8000/health`)
  or the in-browser shell on either service — you cannot reach it from your
  own laptop's browser directly, by design (no public domain).
