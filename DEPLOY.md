# Deploying to Railway

The app is ready to deploy. What follows is the whole process, plus the
three things about *this* app that will bite if they are skipped.

------------------------------------------------------------------------

## Before you start: the three that matter

**1. HTTPS is not optional.** Browser geolocation refuses to return a
position on plain HTTP. Railway gives every service an HTTPS domain, so
this is handled — but it is why the app cannot simply be run on a LAN IP.

**2. `TRUSTED_PROXY_COUNT` must be `1`.** Railway terminates TLS at its
edge, so every request reaches the app from Railway's address, not the
student's. The classroom network check would then compare the wrong
address. Setting this to `1` tells the app to read the real client
address from the last hop of `X-Forwarded-For`.

Do not set it higher than the number of proxies actually in front of the
app. The header is client-writable, and each extra hop you claim is one
the client gets to forge.

**3. The classroom's network must be re-registered.** The seeded
classroom allows loopback and private LAN ranges, which is right for a
laptop demo and meaningless in production. Once deployed, students arrive
from the **college's public egress IP**. Find it by opening
`https://api.ipify.org` on the college Wi-Fi, then set it on the
classroom in **Admin → Classrooms**.

Until that is done, attendance fails closed with
`NETWORK_NOT_CONFIGURED` or `WRONG_NETWORK` — deliberately, since a
misconfigured network check that silently allowed everyone would be worse.

------------------------------------------------------------------------

## Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "GPS self-attendance system"
git branch -M main
git remote add origin https://github.com/<you>/gps-attendance.git
git push -u origin main
```

`.gitignore` already excludes `.env`, `venv/` and `*.db`, so your local
relaxed settings and demo database stay off GitHub.

------------------------------------------------------------------------

## Step 2 — Create the Railway project

1. railway.app → **New Project** → **Deploy from GitHub repo**
2. Pick the repository. Railway detects Python and installs
   `requirements.txt` automatically.
3. It reads `Procfile` for the start command and `.python-version` for
   the interpreter. Nothing to configure.

------------------------------------------------------------------------

## Step 3 — Add Postgres

In the project: **New** → **Database** → **Add PostgreSQL**.

Railway injects `DATABASE_URL` into your service automatically. The app
rewrites the scheme to `postgresql+psycopg://` on startup, so no change
is needed at your end.

------------------------------------------------------------------------

## Step 4 — Set the environment variables

**Variables** tab on the web service. These are the production values —
note that several differ from the local `.env`, which is relaxed so the
app can be demoed on a laptop.

```
SECRET_KEY=<paste a long random string>

# Geofence — production values, NOT the relaxed local ones
GEOFENCE_RADIUS_METERS=10
ACCURACY_CREDIT_METERS=35
MAX_ACCURACY_METERS=50

ANCHOR_ON_TEACHER_LOCATION=true
ANCHOR_ACCURACY_CREDIT_METERS=25
MAX_ANCHOR_ACCURACY_METERS=30

# Attendance window
DEFAULT_WINDOW_SECONDS=120
MAX_WINDOW_SECONDS=300

# Rotating QR token
TOKEN_ROTATION_SECONDS=30
TOKEN_TTL_SECONDS=35

# Anti-proxy — all three must stay on
ENFORCE_NETWORK_CHECK=true
ENFORCE_DEVICE_BINDING=true
FLAG_SUSPICIOUS_RECORDS=false

# Required behind Railway's proxy. See note 2 above.
TRUSTED_PROXY_COUNT=1

# Cookies must be HTTPS-only in production
SESSION_COOKIE_SECURE=true

MAX_ATTEMPTS_PER_SESSION=10
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

`SECRET_KEY` signs the device-binding cookies. Changing it later
invalidates every registered device and forces the whole class to
re-register, so set it once and leave it.

------------------------------------------------------------------------

## Step 5 — Generate a domain

**Settings** → **Networking** → **Generate Domain**. You get something
like `gps-attendance-production.up.railway.app`, with HTTPS already
working. That is the address students use.

------------------------------------------------------------------------

## Step 6 — Create the first accounts

Tables are created automatically on first boot. The accounts are not —
seeding is a deliberate action, since it writes known passwords.

From your machine, with the Railway CLI:

```bash
npm i -g @railway/cli
railway login
railway link
railway run flask --app app seed
```

`railway run` executes locally but with the deployed environment, so it
writes to the production Postgres.

**Change the seeded passwords immediately** — they are published in this
repository. Log in as admin and use **Admin → Teachers** and
**Admin → Students** to create your real accounts, then deactivate the
demo ones.

------------------------------------------------------------------------

## Step 7 — Configure the real classroom

Log in as admin on the Railway URL:

1. **Admin → Classrooms → Add a classroom.** Stand in the actual room,
   press **Use my current location**, set radius `10`.
2. Set **Allowed networks** to the college's public egress IP (step 3 in
   the notes above).
3. **Admin → Overview** warns you about any classroom still missing a
   network.

Because the geofence centres on the teacher when they open the window,
the saved coordinates are only a fallback — but the network entry is not
optional.

------------------------------------------------------------------------

## Afterwards

Push to `main` and Railway redeploys. Postgres data survives redeploys;
run this after any deploy that adds a column:

```bash
railway run flask --app app upgrade-db
```

Watch **Deployments → Logs** on the first boot. The app warns loudly
about weak configuration — a default `SECRET_KEY`, relaxed accuracy
limits, disabled anti-proxy layers, or `TRUSTED_PROXY_COUNT=0` behind a
proxy. A clean start prints none of those.

### Cost

Railway is credit-based rather than a permanent free tier. This app is
small — one web service plus Postgres — but the credit does run out.
Check your usage before relying on it for an end-of-semester demo.
