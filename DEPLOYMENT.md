# DEPLOYMENT.md — How to Actually Run This Thing

Written for someone doing this for the first time. No step assumes you
already know the previous step's jargon — if a word is new, it's explained
right where it first shows up.

## The 30-second mental model

You need **one small always-on computer** (called a "server" or "VPS" —
Virtual Private Server, just a computer you rent that never turns off) that
will run n8n AND has Python installed on it. Everything else (the database,
the AI, the Google Sheet) is a cloud service you sign up for separately and
just *connect* to from that one server.

```
┌─────────────────────────────────────────────────┐
│  YOUR SERVER (the one thing you rent/host)       │
│  ┌───────────────┐        ┌──────────────────┐  │
│  │  n8n           │──runs─▶│  python/ folder   │  │
│  │  (the workflows)│  a    │  (the actual logic)│  │
│  └───────────────┘ command └──────────────────┘  │
└─────────────────┬─────────────────────┬───────────┘
                   │                     │
                   ▼                     ▼
          ┌─────────────────┐   ┌──────────────────┐
          │  Supabase        │   │  Gemini / Groq    │
          │  (the database,  │   │  (the AI that      │
          │   free, cloud)   │   │   writes messages)  │
          └─────────────────┘   └──────────────────┘

  Separately, not on your server:
  - Google Sheet (where you type in new leads)
  - dashboard/index.html (just open it in a browser, anywhere)
```

That's the whole picture. Now let's build it, one piece at a time.

---

## Part 1 — The database (Supabase). Do this first.

1. Go to supabase.com, sign up (free), click "New Project."
2. Wait ~2 minutes for it to spin up.
3. In the left sidebar, click **SQL Editor** → **New query**.
4. Open `database/schema.sql` from this repo, copy ALL of it, paste it into
   the SQL editor, click **Run**. This creates every table.
5. Do the same with `database/seed.sql` if you want two sample leads to
   practice with (optional but recommended for your first test run).
6. In the left sidebar, click **Project Settings → API**. You'll see two
   things you need later — **write them down somewhere**:
   - **Project URL** (looks like `https://abcxyz.supabase.co`)
   - **service_role key** (a long secret string — NOT the "anon" key,
     the service_role one. This is your database's master password,
     never share it or put it in a public place.)

You now have a working database with no server needed for it — Supabase
hosts it for you, free tier is plenty for this project's scale.

---

## Part 2 — Get your AI keys (also free tier)

You need at least one of these (the system tries Gemini first, falls back
to Groq if Gemini fails):

1. **Gemini:** go to aistudio.google.com → Get API key → copy it.
2. **Groq:** go to console.groq.com → API Keys → create one → copy it.

Write both down. Free tier limits on both are generous enough for a small
outbound campaign.

---

## Part 3 — Get a server for n8n + Python

This is the one part of the system that isn't free-free — but it's cheap.
Two real options, pick one:

### Option A — truly ₦0, more fiddly (Oracle Cloud "Always Free")
Oracle gives away a small virtual server forever, no credit card charge
(they ask for a card on file but never charge it unless you upgrade). The
catch: sometimes their free capacity is full in your region and you have
to retry sign-up, and if your server sits completely idle for a long time
they can reclaim it. Search "Oracle Cloud Always Free tier setup" for a
current walkthrough — by the time you read this their exact steps may have
changed slightly, so follow their live docs, not a screenshot from 2025.

### Option B — a few dollars a month, much less fiddly (recommended)
A small VPS from DigitalOcean, Hetzner, or Contabo runs **roughly $4-6 a
month**. For a business tool that needs to run every 15-30 minutes, all
day, this is the option I'd actually pick — Option A's occasional
"your server got reclaimed" surprise is a bad thing to discover the day
you're supposed to be sending messages.

Either way, when you create the server, choose:
- **Ubuntu 22.04 or 24.04** as the operating system
- At least **1 GB of RAM** (2 GB is safer)

You'll get an IP address and a way to connect to it (usually SSH — think
of it as a remote terminal window into that computer).

---

## Part 4 — Install n8n and Python on that server

Connect to your server (your VPS provider will show you exactly how — 
usually a button that opens a terminal, or an SSH command to run from your
own computer). Then run these commands one at a time:

```bash
# Install Docker (this is what runs n8n in an isolated, easy-to-manage box)
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Python and pip (this is what runs the python/ folder's code)
apt update
apt install -y python3 python3-pip git
```

Now get this repo onto the server:

```bash
mkdir -p /opt/hooze-outbound
cd /opt/hooze-outbound
# upload the repo here — easiest way if you don't use git: use `scp` from
# your own computer to copy the whole hooze-outbound folder onto the
# server at this exact path, since every n8n workflow in this repo is
# already written expecting the code to live at /opt/hooze-outbound
```

(If you're comfortable with git: push this repo to a private GitHub repo
first, then `git clone` it onto the server at that same path instead.)

Install the Python dependencies:

```bash
cd /opt/hooze-outbound
pip3 install -r python/requirements.txt --break-system-packages
```

Quick sanity check that Python side works before moving on:

```bash
cd /opt/hooze-outbound
python3 -m pytest tests/ -q
```

You should see `56 passed`. If you do, the Python layer is correctly
installed and working — this doesn't touch Supabase yet, it's just proving
the code itself runs on this machine.

---

## Part 5 — Run n8n itself (Docker)

Still on the server:

```bash
mkdir -p /opt/n8n
cd /opt/n8n
```

Create a file called `docker-compose.yml` there (use `nano docker-compose.yml`
to open a simple text editor, paste this in, then Ctrl+O, Enter, Ctrl+X to
save and exit):

```yaml
version: "3.8"
services:
  n8n:
    image: n8nio/n8n:latest
    restart: always
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=CHANGE_THIS_TO_SOMETHING_ONLY_YOU_KNOW
      # These next 6 lines are the KEY step everyone misses: this is how
      # n8n's Execute Command nodes can see your credentials when they
      # run `python3 -m python.scoring.engine ...` — a .env file on its
      # own does NOTHING here, because n8n runs inside this Docker
      # container, not directly on the server. These environment
      # variables are what actually reaches the Python scripts.
      - SUPABASE_URL=https://your-project.supabase.co
      - SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
      - AI_PROVIDER=gemini
      - GEMINI_API_KEY=your-gemini-key-here
      - GROQ_API_KEY=your-groq-key-here
    volumes:
      - n8n_data:/home/node/.n8n
      - /opt/hooze-outbound:/opt/hooze-outbound   # <- lets n8n's Execute
                                                    #    Command reach the
                                                    #    python/ folder
volumes:
  n8n_data:
```

Fill in your real Supabase URL/key and AI keys from Parts 1-2. Then start it:

```bash
docker compose up -d
```

n8n is now running. Visit `http://YOUR_SERVER_IP:5678` in your browser —
you should see the n8n login screen (use the admin/password you set
above). For real use you'll want a domain name + HTTPS in front of this
eventually, but for getting it working, the IP address is fine to start.

**One catch:** the volume line above (`/opt/hooze-outbound:/opt/hooze-outbound`)
makes the Python folder visible *inside* the n8n container at that same
path, but Python itself also needs to be *installed inside that container*
for Execute Command to run `python3`. The official n8n Docker image doesn't
include Python by default. Simplest fix: instead of using Execute Command
nodes to call `python3` inside the n8n container, point every Execute
Command node's command at a path where Python runs on the **host** server
via SSH, OR (much simpler in practice) skip Docker for n8n and install n8n
directly on the server with `npm install -g n8n` instead — then n8n and
your already-installed Python share the same machine with no container
boundary to worry about:

```bash
apt install -y nodejs npm
npm install -g n8n
n8n start
```

If you go this route, use `pm2` (a small tool that keeps programs running
forever in the background) so n8n survives you closing your terminal:

```bash
npm install -g pm2
pm2 start n8n
pm2 save
pm2 startup   # follow the one command it prints to make this survive reboots
```

And set the environment variables directly on the server instead of in
Docker Compose — add these lines to `/etc/environment` (edit with
`nano /etc/environment`), then reboot the server once:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
AI_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key-here
GROQ_API_KEY=your-groq-key-here
```

Either approach (Docker with Python added into the image, or plain
npm-installed n8n) works — the npm approach is genuinely simpler for a
first deployment, which is why it's the fallback here.

---

## Part 6 — Import the workflows

1. Open n8n in your browser (`http://YOUR_SERVER_IP:5678`).
2. For each file in `n8n/WF-*.json` (all 15): click **Workflows → Import
   from File**, select it.
3. On any node that mentions Supabase, click it, and set up a Supabase
   credential once (n8n will ask for your Project URL + service_role key
   from Part 1) — after the first one, reuse the same credential on every
   other Supabase node.
4. Double check every "Execute Command" node's command starts with
   `cd /opt/hooze-outbound && python3 ...` — if you put the repo somewhere
   else, edit this path in every node (or better: just put the repo at
   exactly `/opt/hooze-outbound` to match what's already there).
5. Toggle each workflow **Active** (top-right switch) once you're happy
   with it. WF-01 needs your Google Sheet set up first (Part 7) before
   it's useful.
6. For WF-09, WF-10, WF-12, WF-13 (the ones with a Webhook trigger, not a
   Schedule trigger): after activating, click the Webhook node, copy the
   **Production URL** shown — you'll need these for the dashboard (Part 8)
   and for wiring up inbound WhatsApp/email replies (WF-12).

---

## Part 7 — Set up the Google Sheet

Follow `external-templates/README.md` exactly — it walks through creating
the sheet, naming the two tabs, and where to paste the Sheet ID into WF-01.

---

## Part 8 — The dashboard

`dashboard/index.html` is just a file — no server, no build step. Two ways
to use it:
- **Simplest:** just double-click it to open in your browser. Works fine
  for a single operator on their own computer.
- **If you want it accessible from anywhere:** drag-and-drop the file onto
  netlify.com (free), or push it to a GitHub repo and enable GitHub Pages
  (free) — both give you a URL you can open from your phone too.

Open the file in a text editor, find the `WEBHOOKS` section near the top
of the `<script>` tag, and paste in the three webhook URLs you copied in
Part 6 (WF-09, WF-10, WF-13).

---

## Part 9 — Test it end-to-end before trusting it with real leads

1. In the Google Sheet's `Staging` tab, add one test row (name +
   industry=`Real Estate` + location=`Abuja`, matching Campaign 001).
2. Manually run WF-01 in n8n (click "Execute Workflow" instead of waiting
   for the schedule) — check Supabase's `companies` table for a new row.
3. Manually run WF-02 through WF-06 in order the same way, checking
   Supabase after each one.
4. Open the dashboard — your test lead should eventually show up in the
   Review Queue once it's scored high enough and personalized.
5. Once that whole chain works for one fake lead, turn on the schedules
   (the workflows will now run themselves every 15-30 minutes as designed)
   and start feeding it real leads.

---

## Quick troubleshooting

- **"Execute Command node fails"** → almost always means the repo isn't
  at the exact path the command expects, or `pip install` wasn't run, or
  Python isn't installed where n8n can see it. SSH into the server and
  manually run the exact command from the node to see the real error.
- **"AIError" in results** → your Gemini/Groq key is missing or wrong.
  Check the environment variables are actually set where n8n's process can
  see them (this is the #1 thing people get wrong — a `.env` file sitting
  in `/opt/hooze-outbound` does NOT automatically get read by n8n itself,
  only by Python when it's run directly with `python-dotenv` installed;
  n8n needs the variables set in ITS OWN environment, per Part 5).
- **"Nothing happens, no errors either"** → check the workflow is actually
  toggled **Active**, and check the Schedule Trigger's timing hasn't just
  not fired yet.
