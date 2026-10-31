# AuditSum

A governed LLM summarization service — built to prove **what was allowed, what happened, and where every output came from**, not just to produce a summary.

**Live demo:** https://auditsum.onrender.com _(Render's free tier sleeps after ~15 min idle — first load may take ~30–60s to wake up)_

Most AI summarizer projects stop at "upload a file, call an LLM, show the result." This one treats that as the easy part. The actual project is the layer around the LLM call: role-based access control, a policy engine that runs before any document is processed, a hash-chained audit log that makes tampering mathematically detectable, and citation verification that catches the model when it claims a quote that isn't actually in the source.

---

## Why this exists

Most portfolio AI projects are thin wrappers around an API call. This one is built around a different question: **can you prove what an AI system did, and catch it when something goes wrong?** That's the problem real governance, compliance, and security teams actually have with LLM deployments — and it's deliberately the center of this project, not an afterthought.

---

## What's actually built (vs. aspirational)

This README describes what's implemented and tested, not a wishlist. A few things from the original design doc were deliberately simplified or deferred — see [Known limitations](#known-limitations) for an honest list.

### Control
- **Role-based access control** — `user`, `admin`, `auditor` roles, enforced per-endpoint, tested for all three outcomes (allowed / not logged in / wrong role).
- **Policy engine** — every document upload runs through ordered checks: admin kill switch → file type allowlist → size limit → PII scan (regex-based email/phone detection with redaction). Every decision, allow or deny, is recorded and audited.
- **Admin kill switch** — a `controls` table lets an admin disable a model at runtime; the policy engine checks it first, before anything else.
- **Daily token circuit breaker** — once a configured daily token budget is hit, new runs automatically fall back to a deterministic mock provider instead of failing or continuing to spend real API quota. The breaker only counts real-provider usage, not mock-fallback runs, so it can't inflate itself.
- **Per-IP rate limiting** on the endpoints that actually cost LLM quota.

### Auditing
- **Hash-chained, append-only audit log.** Every meaningful action (login, upload, policy decision, LLM call, run completion) is written as an event whose hash includes the previous event's hash — tampering with any row breaks the chain from that point forward.
- **Database-enforced immutability.** A Postgres trigger rejects `UPDATE`/`DELETE` on the audit table outright, independent of the application code.
- **`/audit/verify`** walks the entire chain and reports either a clean bill of health or the exact sequence number where something broke.
- **Concurrency-safe writes** via a Postgres advisory lock, so simultaneous requests can't fork the chain.
- **Proven, not just claimed:** tested by manually editing a row in the database and confirming verification catches it, names the broken row, and recovers once the data is restored.

### Traceability
- **Every run is fully reconstructable:** input hash, provider, model, strategy, token counts, and a full step-by-step record of what was sent to the LLM and what came back.
- **Map-reduce for long documents.** Documents are chunked on paragraph boundaries with overlap; each chunk is summarized independently, then combined in a final reduce step. Strategy selection (single-call vs. map-reduce) is itself a recorded, explainable decision.
- **Citation verification.** The model is asked to support every key point with an exact quote from the source. Each quote is checked as a real substring of the original text (after Unicode/whitespace normalization) — not just trusted. Verified and unverified citations are both shown, with a verification rate computed per run.

### The pipeline
- Real LLM calls via Groq (`gpt-oss-120b`), with a swappable provider interface — a mock provider (deterministic, can simulate hallucinated quotes on demand) is used in development and as the circuit-breaker fallback.
- Retry with exponential backoff on rate limits; one repair attempt on malformed JSON output before failing the run cleanly with a recorded reason.
- Structured JSON output (title, summary, key points with quotes, action items), validated and parsed, not just displayed as raw text.

### The UI
A server-rendered interface (FastAPI + Jinja2), not just a Swagger page:
- Login/logout with signed session cookies, with full audit logging on both.
- Upload → see live policy decisions → run a summary → see the result with verified/unverified citation badges and the full step lineage.
- An **auditor console**: a sidebar into every underlying table (audit events, documents, runs, policy decisions, citations) with a "Verify Chain" button showing a live pass/fail banner.
- An **admin page**: all users, all documents, all runs, and current kill-switch controls.
- Role-aware navigation — links only appear for roles that can actually use them.
- Unauthenticated visits to any UI page redirect cleanly to login with an explanatory message, rather than showing a raw error.

---

## Architecture

```
Browser (Jinja2 + server-rendered HTML)
        │
        ▼
   FastAPI app ──► RBAC ──► Policy Engine ──► Pipeline ──► LLM Provider
        │                        │                │         (Groq / Mock)
        │                        ▼                ▼
        └──────────────────► Audit Log (hash-chained, Postgres-enforced)
                                 │
                                 ▼
                          PostgreSQL (Neon)
```

- **Backend:** FastAPI, SQLAlchemy 2, Alembic migrations
- **Database:** PostgreSQL (Neon, free tier)
- **LLM:** Groq (`gpt-oss-120b`), OpenAI-compatible client, swappable provider interface
- **Auth:** Argon2 password hashing, signed session cookies
- **UI:** Jinja2 server-rendered templates, no separate frontend build
- **Hosting:** Docker container on Render (free tier)
- **Everything runs at zero cost** — free database, free LLM tier, free hosting.

---

## Try it yourself

Three roles to explore with:
- **User** — upload a document, run a summary, see citation verification
- **Admin** — everything a user can do, plus the admin console (users, controls, kill switch)
- **Auditor** — read-only access to every table via the auditor console, plus chain verification

_(Demo credentials: see the live demo landing page.)_

**A good first flow:** log in → upload a `.txt` file → watch the policy engine's decisions appear → run a summary → check which citations verified against the source → log in as admin or auditor → open the Auditor Console → click **Verify Chain**.

---

## Known limitations

Being upfront about these, since a good portfolio project names its trade-offs rather than hiding them:

- **Tamper-evident, not tamper-proof.** Someone with full database access could, in principle, recompute the entire chain. The trigger and hash chain stop casual or accidental tampering and make deliberate tampering detectable — they don't make it physically impossible. External hash anchoring (publishing the latest hash somewhere outside the database) would close this gap further and isn't built yet.
- **Text files only** (`.txt`, `.md`). PDF support is not implemented.
- **PII detection is regex-based**, not a full NLP library like Presidio — a deliberate lightweight choice for a free-tier deployment, with real false-negative/false-positive trade-offs.
- **Citation verification proves the quote exists in the source — not that the model's interpretation of it is fair.** That's a meaningfully narrower (but still genuinely useful) guarantee.
- **The Render free tier sleeps when idle.** The first request after inactivity will be slow. This is a known, accepted trade-off of the free hosting tier, not a bug.
- **Notional token/cost figures**, not billed amounts — useful for the circuit breaker, not an invoice.
- **Some run-execution helper code is informally structured** (plain attributes attached to objects rather than dedicated response types) — a deliberate shortcut in a few places to keep iteration fast, noted rather than hidden.

---

## Project structure

```
app/
├── models.py              # SQLAlchemy models
├── db.py                  # engine/session setup
├── templates.py           # shared Jinja2 instance
├── rate_limit.py           # per-IP rate limiting
├── security/
│   ├── auth.py             # login logic, password hashing, session identity
│   └── rbac.py              # role-check dependency
├── audit/
│   ├── canonical.py         # deterministic JSON serialization
│   ├── hashing.py            # SHA-256 + timestamp helpers
│   ├── service.py             # append_event() — the hash chain writer
│   └── verify.py               # chain verification
├── policy/
│   ├── engine.py             # pure, testable policy checks
│   ├── service.py              # DB + audit wiring around the checks
│   └── pii.py                   # regex-based PII detection/redaction
├── pipeline/
│   ├── tokens.py              # token estimation, strategy selection
│   ├── chunker.py              # paragraph-aware chunking with overlap
│   ├── summarize.py             # map-reduce orchestration
│   ├── citations.py             # quote verification against source text
│   ├── circuit_breaker.py       # daily token cap + mock fallback
│   ├── run_service.py            # the shared run-execution pipeline
│   └── prompts.py                 # system prompts (single, map, reduce)
├── llm/
│   ├── base.py               # provider interface (Protocol)
│   ├── mock.py                 # deterministic mock, can simulate hallucination
│   └── openai_compat.py         # real Groq provider, retry/backoff
└── routes/
    ├── auth.py, documents.py, runs.py, audit.py   # JSON API
    └── ui.py                                       # server-rendered UI

alembic/           # database migrations (schema + Postgres triggers)
templates/          # Jinja2 HTML templates
Dockerfile
```

---

## Running it locally

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
pip install -r requirements.txt
```

Create a `.env` file:
```
DATABASE_URL=postgresql+psycopg://...
GROQ_API_KEY=...
SESSION_SECRET=...
DEMO_DAILY_TOKEN_CAP=50000
RATE_LIMIT_PER_MINUTE=5
```

```bash
alembic upgrade head
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000/ui/login`.

**Docker:**
```bash
docker build -t auditsum .
docker run -p 8000:8000 --env-file .env -e PORT=8000 auditsum
```

---

## What's next

- External hash anchoring (publish the latest chain hash somewhere outside the database)
- A visible "simulated output" banner when the circuit breaker falls back to the mock provider
- Versioned, admin-managed prompt templates
- An approval workflow for policy-flagged documents
- Retrieval-augmented Q&A over a document, with the same audit/citation guarantees as summarization
