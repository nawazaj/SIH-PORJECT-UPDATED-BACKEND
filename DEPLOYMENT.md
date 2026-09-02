# Deploying CivicShield Backend to Render

## 1. What actually matters: the Groq API key, not RAM

Earlier versions of this service loaded several transformer models locally
and needed real RAM headroom for that. That's no longer true — sentiment,
emotion, and sarcasm analysis now run through the **Groq API**
(`app/services/sentiment_service.py`), and misinformation-risk scoring is a
lightweight rule-based heuristic (`app/services/credibility_service.py`)
with no ML model loaded at all. Render's free/starter RAM tiers are fine.

**What actually will bite you instead:** forgetting to set `GROQ_API_KEY` as
an environment variable on the deployed service. Without it, the app runs
fine and returns 200s — it just silently falls back to neutral
sentiment/emotion for every single post, which is a much harder bug to
notice mid-demo than a crash. `render.yaml` declares this variable with
`sync: false`, which means Render will prompt you to paste the value in
the dashboard rather than storing it in the repo — do that before your
first deploy.

## 2. Deploy steps

**Option A — Blueprint (recommended, reproducible):**
1. Push this repo to GitHub.
2. In Render: New → Blueprint → connect your repo. Render will read

   `render.yaml` and provision both the web service and the Postgres
   database automatically.
3. Open `render.yaml` first and change `plan: starter` to `plan: standard`
   for the web service if you want the safer RAM headroom described above.

**Option B — Manual:**
1. New → PostgreSQL. Note the **Internal Database URL** it gives you.
2. New → Web Service → connect your repo.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/health`
   - Environment variable `DATABASE_URL` = the Internal Database URL from step 1
   - Environment variable `GROQ_API_KEY` = your key from https://console.groq.com/keys
     (required — see section 1 above)
   - Environment variable `CORS_ORIGINS` = your frontend's deployed URL
     (e.g. `https://civicshield.vercel.app`) — leave as `*` only for early testing

## 3. Create the tables once

After the first successful deploy, open a Render **Shell** on the web
service and run:
```
python scripts/init_db.py
```
This only needs to run once (it's additive — safe to re-run if you add new
models later, since `Base.metadata.create_all` skips existing tables).

## 4. Connecting your frontend

- Your API base URL will be `https://<your-service-name>.onrender.com/api/v1`
- Interactive docs live at `https://<your-service-name>.onrender.com/docs` —
  useful for your frontend teammate to see exact request/response shapes
  without reading backend code.
- Set `CORS_ORIGINS` (see above) to your actual frontend origin once deployed,
  not `*` — this is a one-line env var change, not a code change.

## 5. Two things worth knowing before demo day

- **Free Postgres expires after 30 days.** Fine for a hackathon timeline,
  but if there's a gap between building and presenting, check the
  expiry date in the Render dashboard.
- **Free/Starter web services spin down after 15 minutes idle** and cold-start
  (~30-60s) on the next request. If your demo has a live judging slot, hit
  the health-check URL a minute or two beforehand to warm it up — or use a
  paid always-on plan for that window.
