# AuditSum: A Governed LLM Summarization Service

> Summarize text files with an LLM, and be able to prove **what was allowed, what happened, and where every output came from**.

The summary is the easy part. This project is about **control**, **auditing**, and **traceability** around an LLM call, built entirely on free and open-source tooling.

---

## Table of Contents

1. [Goals and Non-Goals](#1-goals-and-non-goals)
2. [Feature Overview](#2-feature-overview)
3. [Architecture](#3-architecture)
4. [Tech Stack (Zero Cost)](#4-tech-stack-zero-cost)
5. [Repository Structure](#5-repository-structure)
6. [Data Model](#6-data-model)
7. [Control: RBAC, Policy Engine, Quotas](#7-control-rbac-policy-engine-quotas)
8. [Auditing: Hash-Chained Log](#8-auditing-hash-chained-log)
9. [Traceability: Runs, Lineage, Citations](#9-traceability-runs-lineage-citations)
10. [Summarization Pipeline](#10-summarization-pipeline)
11. [LLM Provider Abstraction](#11-llm-provider-abstraction)
12. [API Specification](#12-api-specification)
13. [UI Plan](#13-ui-plan)
14. [Observability](#14-observability)
15. [Security and Privacy](#15-security-and-privacy)
16. [Testing Strategy](#16-testing-strategy)
17. [Evaluation Harness](#17-evaluation-harness)
18. [Free-Tier Constraints](#18-free-tier-constraints)
19. [Hosting and Public Demo](#19-hosting-and-public-demo)
20. [Milestones](#20-milestones)
21. [Demo Script](#21-demo-script)
22. [Known Limitations](#22-known-limitations)
23. [Definition of Done](#23-definition-of-done)
24. [Optional Stretch: RAG Q&A (Milestone 9)](#24-optional-stretch-rag-qa-milestone-9)

---

## 1. Goals and Non-Goals

### Goals

- Accept `.txt` / `.md` uploads and produce validated, structured summaries using `gpt-oss-120b` (or a mock/local model).
- **Control:** enforce who can do what, which models and prompts are allowed, and how much can be used.
- **Auditing:** record every meaningful event in an append-only, hash-chained log that can be independently verified.
- **Traceability:** for any summary, reconstruct its inputs, prompt version, model, parameters, intermediate steps, and the source passages behind each claim.
- Cost nothing to build, run locally, or **host publicly** so hiring managers can try it without installing anything.
- (Stretch, section 24) Optionally support governed Q&A over a document via retrieval, with the same audit and citation-verification guarantees as summarization.

### Non-Goals

- PDF/OCR/image support (documented as a future extension).
- Multi-tenant SaaS features, billing, or SSO.
- Guaranteeing deterministic LLM output (runs are *recorded*, not guaranteed reproducible).
- Being tamper-*proof*. The audit log is tamper-*evident* (see [Known Limitations](#21-known-limitations)).

---

## 2. Feature Overview

| Pillar | Feature | Summary |
|---|---|---|
| Control | RBAC | Roles: `user`, `admin`, `auditor`; enforced on every endpoint |
| Control | Policy engine | Pre-call checks (size, model allowlist, PII) returning allow / deny / redact with reasons |
| Control | Quotas and budgets | Per-user rate limit and monthly token cap; admin kill switch |
| Control | Versioned prompts | Immutable prompt template versions, admin-managed |
| Control | Approval workflow | Policy-flagged documents wait for admin approval |
| Control | Retention | Delete-my-data removes content but keeps audit metadata |
| Auditing | Append-only log | Every action recorded; DB triggers block UPDATE/DELETE |
| Auditing | Hash chain | Each event includes the previous event's hash |
| Auditing | Verification | `/audit/verify` walks the chain and reports the first broken link |
| Auditing | External anchoring | Latest hash periodically published to a public GitHub repo/Gist |
| Traceability | Run records | Input hash, model, params, prompt version, tokens, latency, trace ID |
| Traceability | Lineage tree | Chunk → chunk-summary → final summary, fully stored |
| Traceability | Verified citations | Each key point carries a quote; quotes are string-matched to the source |
| Traceability | Trace IDs | OpenTelemetry trace ID appears in logs, DB rows, and UI |
| Traceability | Run diff | Compare two runs of the same document side by side |
| Stretch (M9) | RAG Q&A | Ask questions over a document; retrieval is audited and answers carry verified citations |

---

## 3. Architecture

```mermaid
flowchart LR
    U[Browser: Jinja + HTMX] -->|HTTPS| API[FastAPI App]
    API --> AUTH[Auth + RBAC]
    API --> POL[Policy Engine]
    API --> PIPE[Summarization Pipeline]
    PIPE --> LLM[LLM Provider Interface]
    LLM --> P1[Groq / OpenRouter: gpt-oss-120b]
    LLM --> P2[Ollama: gpt-oss-20b]
    LLM --> P3[Mock Provider]
    AUTH --> AUD[Audit Service]
    POL --> AUD
    PIPE --> AUD
    AUD --> DB[(PostgreSQL)]
    PIPE --> DB
    API --> OTEL[OpenTelemetry]
    AUD -.periodic anchor.-> GH[Public GitHub Repo]
```

### Request lifecycle (summarize)

1. Authenticate; check role permission. Log `auth.*`.
2. Validate upload (type, size, encoding). Store content; compute SHA-256. Log `document.uploaded`.
3. Run policy engine. Log every `policy.decision`.
4. If denied, stop. If flagged, set status `pending_approval` and stop until an admin acts.
5. Check quota; reserve tokens.
6. Create a `runs` row. Execute pipeline (single call or map-reduce), writing a `run_steps` row per LLM call. Log `llm.call.*` events.
7. Validate structured output; verify citations. Store results.
8. Finalize run, update usage, log `run.completed`.

---

## 4. Tech Stack (Zero Cost)

| Concern | Choice | Notes |
|---|---|---|
| Language | Python 3.12 | |
| Web framework | FastAPI | Async, automatic OpenAPI docs |
| UI | Jinja2 templates + HTMX | No separate frontend build |
| Database | **PostgreSQL** (your existing instance; local Docker Postgres for tests) | Real triggers, roles, advisory locks, JSONB |
| DB driver | `psycopg` 3 (sync) or `asyncpg` | Use `sslmode=require` for hosted instances |
| ORM / migrations | SQLAlchemy 2 + Alembic | Triggers, functions, and grants live in migrations |
| Validation | Pydantic v2 | Also validates LLM JSON |
| Auth | Sessions or JWT, `argon2-cffi` hashing | No third-party auth |
| LLM (primary) | `gpt-oss-120b` via Groq or OpenRouter free tier | OpenAI-compatible client |
| LLM (offline) | `gpt-oss-20b` via Ollama | Needs roughly 16 GB RAM |
| LLM (tests) | Mock provider | Deterministic |
| PII detection | Microsoft Presidio (or regex fallback) | |
| Token counting | `tiktoken` or chars/4 estimate | Estimate is fine for gating |
| Rate limiting | `slowapi` or a small in-house limiter | |
| Tracing | OpenTelemetry SDK, console/file exporter, optional Jaeger in Docker | |
| Testing | pytest, pytest-asyncio, hypothesis | |
| Lint / types | ruff, mypy | |
| CI | GitHub Actions (free for public repos) | |
| Packaging | Docker + docker compose | |
| Hosting | Hugging Face Spaces (Docker) or Render free tier | Or run locally and record a demo video |

---

## 5. Repository Structure

```
auditsum/
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── alembic/
│   └── versions/                # includes trigger + function migrations
├── db/
│   └── roles.sql                # owner/app role creation and grants (run once as admin)
├── app/
│   ├── main.py                  # FastAPI app factory
│   ├── config.py                # settings (pydantic-settings)
│   ├── db.py                    # engine, session, transaction helpers
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic request/response models
│   ├── security/
│   │   ├── auth.py              # login, sessions, password hashing
│   │   └── rbac.py              # role → permission map, dependency
│   ├── audit/
│   │   ├── service.py           # append_event(), canonicalization, hashing
│   │   ├── verify.py            # chain verification
│   │   └── anchor.py            # publish latest hash externally
│   ├── policy/
│   │   ├── engine.py            # runs ordered checks, returns decisions
│   │   ├── checks.py            # size, model allowlist, PII, kill switch
│   │   └── quota.py             # rate limits and token budgets
│   ├── pipeline/
│   │   ├── ingest.py            # validation, encoding detection, hashing
│   │   ├── tokens.py            # token estimation
│   │   ├── chunker.py           # paragraph/sentence chunking with overlap
│   │   ├── summarize.py         # single-call and map-reduce orchestration
│   │   └── citations.py         # quote verification
│   ├── llm/
│   │   ├── base.py              # LLMProvider protocol
│   │   ├── openai_compat.py     # Groq / OpenRouter / Ollama
│   │   └── mock.py
│   ├── routes/
│   │   ├── auth.py
│   │   ├── documents.py
│   │   ├── runs.py
│   │   ├── audit.py
│   │   └── admin.py
│   ├── observability/
│   │   └── tracing.py
│   ├── templates/               # Jinja2
│   └── static/
├── scripts/
│   ├── seed_demo.py
│   ├── tamper_demo.py           # edits an audit row to show verification failure
│   └── anchor_cron.py
├── eval/
│   ├── corpus/                  # public-domain texts (Project Gutenberg)
│   ├── rubric.yaml
│   └── run_eval.py
└── tests/
    ├── unit/
    ├── integration/
    └── property/
```

---

## 6. Data Model

Written for **PostgreSQL 14+**. Design rules that matter for the audit guarantees:

- `audit_events` stores `ts` and `payload_json` as **TEXT**, not `TIMESTAMPTZ` / `JSONB`. Postgres normalizes JSONB (key order, whitespace) and timestamps (precision, timezone), which would silently change what gets hashed. The application writes the canonical strings once and they are never reinterpreted.
- Everything else uses native types (`JSONB`, `TIMESTAMPTZ`, `BOOLEAN`).
- `audit_events.seq` is **not** an identity/serial column. Sequences leave gaps on rolled-back transactions, and gaps would be indistinguishable from deleted rows. The application assigns `seq = last + 1` under a lock.

### 6.1 Tables

```sql
-- Identity
CREATE TABLE users (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('user','admin','auditor')),
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Documents (content is separable from metadata for retention)
CREATE TABLE documents (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  owner_id      BIGINT NOT NULL REFERENCES users(id),
  filename      TEXT NOT NULL,
  sha256        CHAR(64) NOT NULL,
  size_bytes    INTEGER NOT NULL,
  encoding      TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN
                  ('uploaded','pending_approval','approved','denied','content_deleted')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  content_deleted_at TIMESTAMPTZ
);
CREATE INDEX documents_owner_idx ON documents(owner_id);

CREATE TABLE document_contents (
  document_id   BIGINT PRIMARY KEY REFERENCES documents(id),
  text          TEXT NOT NULL              -- deleted on retention request
);

-- Versioned, immutable prompts
CREATE TABLE prompt_templates (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name          TEXT NOT NULL,
  version       INTEGER NOT NULL,
  body          TEXT NOT NULL,
  body_sha256   CHAR(64) NOT NULL,
  created_by    BIGINT NOT NULL REFERENCES users(id),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  is_active     BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (name, version)
);
-- At most one active version per prompt name
CREATE UNIQUE INDEX prompt_one_active_idx ON prompt_templates(name) WHERE is_active;

-- One summarization attempt
CREATE TABLE runs (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id     BIGINT NOT NULL REFERENCES documents(id),
  requested_by    BIGINT NOT NULL REFERENCES users(id),
  prompt_id       BIGINT NOT NULL REFERENCES prompt_templates(id),
  replay_of       BIGINT REFERENCES runs(id),
  provider        TEXT NOT NULL,
  model           TEXT NOT NULL,
  params_json     JSONB NOT NULL,           -- temperature, reasoning_effort, style, length
  strategy        TEXT NOT NULL CHECK (strategy IN ('single','map_reduce')),
  input_sha256    CHAR(64) NOT NULL,
  status          TEXT NOT NULL CHECK (status IN
                    ('queued','running','succeeded','failed','blocked')),
  trace_id        TEXT,
  total_prompt_tokens     INTEGER NOT NULL DEFAULT 0,
  total_completion_tokens INTEGER NOT NULL DEFAULT 0,
  notional_cost_usd       NUMERIC(12,6) NOT NULL DEFAULT 0,
  latency_ms      INTEGER,
  result_json     JSONB,                    -- validated structured summary
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ
);
CREATE INDEX runs_document_idx ON runs(document_id);
CREATE INDEX runs_trace_idx ON runs(trace_id);

-- Every LLM call (and chunk) inside a run
CREATE TABLE run_steps (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id          BIGINT NOT NULL REFERENCES runs(id),
  step_index      INTEGER NOT NULL,
  kind            TEXT NOT NULL CHECK (kind IN ('single','map','reduce')),
  parent_step_ids BIGINT[] NOT NULL DEFAULT '{}',   -- which steps fed this one
  chunk_start     INTEGER,                          -- char offsets into the source
  chunk_end       INTEGER,
  input_sha256    CHAR(64) NOT NULL,
  output_text     TEXT,
  prompt_tokens   INTEGER,
  completion_tokens INTEGER,
  latency_ms      INTEGER,
  attempts        INTEGER NOT NULL DEFAULT 1,
  error           TEXT,
  trace_span_id   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (run_id, step_index)
);

-- Each policy check outcome
CREATE TABLE policy_decisions (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id   BIGINT REFERENCES documents(id),
  run_id        BIGINT REFERENCES runs(id),
  check_name    TEXT NOT NULL,
  outcome       TEXT NOT NULL CHECK (outcome IN ('allow','deny','redact','flag')),
  reason        TEXT NOT NULL,
  details_json  JSONB,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Verified citations
CREATE TABLE citations (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id        BIGINT NOT NULL REFERENCES runs(id),
  key_point     TEXT NOT NULL,
  quote         TEXT NOT NULL,
  verified      BOOLEAN NOT NULL,           -- TRUE if found in source
  match_type    TEXT NOT NULL DEFAULT 'exact' CHECK (match_type IN ('exact','approximate','none')),
  char_start    INTEGER,
  char_end      INTEGER
);

-- Usage accounting
CREATE TABLE usage_ledger (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id),
  run_id        BIGINT REFERENCES runs(id),
  tokens        INTEGER NOT NULL,
  period        CHAR(7) NOT NULL,           -- e.g. '2026-10'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_user_period_idx ON usage_ledger(user_id, period);

-- Admin-controlled switches
CREATE TABLE controls (
  key           TEXT PRIMARY KEY,           -- e.g. 'model:gpt-oss-120b:enabled'
  value         TEXT NOT NULL,
  updated_by    BIGINT REFERENCES users(id),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The audit log (see section 8)
CREATE TABLE audit_events (
  seq            BIGINT PRIMARY KEY,        -- assigned by the app under a lock; no gaps allowed
  ts             TEXT NOT NULL,             -- canonical UTC ISO-8601, fixed microsecond precision
  actor_id       BIGINT,                    -- NULL for system
  actor_role     TEXT,
  action         TEXT NOT NULL,
  entity_type    TEXT,
  entity_id      BIGINT,
  request_id     TEXT,
  trace_id       TEXT,
  payload_json   TEXT NOT NULL,             -- canonical JSON string; metadata and hashes only
  payload_sha256 CHAR(64) NOT NULL,
  prev_hash      CHAR(64) NOT NULL,
  hash           CHAR(64) NOT NULL UNIQUE
);
CREATE INDEX audit_action_idx ON audit_events(action);
CREATE INDEX audit_trace_idx  ON audit_events(trace_id);
CREATE INDEX audit_entity_idx ON audit_events(entity_type, entity_id);
```

### 6.2 Database-enforced immutability and chain continuity

Three layers, so the guarantee does not rely on application code alone:

```sql
-- Layer 1: block UPDATE / DELETE / TRUNCATE for everyone, including the table owner
CREATE FUNCTION audit_events_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only (% blocked)', TG_OP;
END $$;

CREATE TRIGGER audit_no_update_delete
  BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_immutable();

CREATE TRIGGER audit_no_truncate
  BEFORE TRUNCATE ON audit_events
  FOR EACH STATEMENT EXECUTE FUNCTION audit_events_immutable();

-- Layer 2: reject any insert that does not continue the chain
CREATE FUNCTION audit_events_check_chain() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE last_row audit_events%ROWTYPE;
BEGIN
  PERFORM pg_advisory_xact_lock(727001);   -- same key the app uses (re-entrant in one session)
  SELECT * INTO last_row FROM audit_events ORDER BY seq DESC LIMIT 1;
  IF NOT FOUND THEN
    IF NEW.seq <> 1 OR NEW.prev_hash <> repeat('0', 64) THEN
      RAISE EXCEPTION 'invalid genesis event';
    END IF;
  ELSIF NEW.seq <> last_row.seq + 1 OR NEW.prev_hash <> last_row.hash THEN
    RAISE EXCEPTION 'chain continuity violated at seq %', NEW.seq;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER audit_chain_check
  BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_events_check_chain();
```

Layer 3 is **privilege separation** (`db/roles.sql`, run once by an admin):

```sql
CREATE ROLE auditsum_app LOGIN PASSWORD :'app_password';   -- what the running app uses
-- Migrations run as the owner role (your existing DB user); the app never uses it.

GRANT USAGE ON SCHEMA public TO auditsum_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  users, documents, document_contents, prompt_templates, runs, run_steps,
  policy_decisions, citations, usage_ledger, controls TO auditsum_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO auditsum_app;

-- Audit log: read and append only
GRANT SELECT, INSERT ON audit_events TO auditsum_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM auditsum_app;
```

Apply the same immutability trigger pattern to `policy_decisions` and to `prompt_templates` body columns (new versions only, never edits).

> **Hosted Postgres note:** if your provider does not let you create roles, keep Layers 1 and 2; the triggers still protect the log from the app. Layer 3 then becomes a documented recommendation. Either way, remember the table **owner** can disable triggers, so the tamper demo (section 21) deliberately does exactly that to show that the hash chain still catches it.

## 7. Control: RBAC, Policy Engine, Quotas

### 7.1 Permission matrix

| Action | user | admin | auditor |
|---|:---:|:---:|:---:|
| Upload document | ✅ | ✅ | ❌ |
| Run summary on own document | ✅ | ✅ | ❌ |
| View own runs | ✅ | ✅ | ✅ (all, read-only) |
| View others' runs | ❌ | ✅ | ✅ |
| View audit log | ❌ | ✅ | ✅ |
| Verify audit chain | ❌ | ✅ | ✅ |
| Approve / deny flagged docs | ❌ | ✅ | ❌ |
| Create prompt version | ❌ | ✅ | ❌ |
| Toggle model/user kill switch | ❌ | ✅ | ❌ |
| Delete own document content | ✅ | ✅ | ❌ |
| Modify audit data | ❌ | ❌ | ❌ |

Implement as a `require(permission)` FastAPI dependency. A **deny by default** map means any new endpoint without an explicit permission fails tests.

Separation of duties: the auditor cannot change anything, and admins cannot delete audit events (no one can).

### 7.2 Policy engine

Checks run in a fixed order; each returns `PolicyDecision(check_name, outcome, reason, details)` and every decision is stored **and** audited.

| Order | Check | Outcome examples |
|---|---|---|
| 1 | Kill switch (user disabled, model disabled) | deny |
| 2 | File type and extension allowlist | deny |
| 3 | Size limit (e.g. 1 MB, ~250k chars) | deny |
| 4 | Encoding validity | deny |
| 5 | Model + reasoning-effort allowlist | deny |
| 6 | PII scan (email, phone, SSN-like, credit card via Luhn, names via Presidio) | allow / redact / flag |
| 7 | Quota: requests per minute, monthly tokens | deny |
| 8 | Demo global daily token cap (circuit breaker, section 19.4) | deny, or fall back to the mock provider |

Policy modes for PII (configurable per deployment): `block`, `redact` (replace with `[EMAIL_1]` and store the redaction map hash only), or `flag` (route to admin approval).

The engine is pure and deterministic: `evaluate(context) -> list[PolicyDecision]`, which makes it easy to unit-test exhaustively.

### 7.3 Quotas and kill switch

- Rate limit: N runs per user per minute.
- Monthly budget: token cap per user recorded in `usage_ledger`.
- Reserve estimated tokens before the call and reconcile with actual usage afterward.
- Admins can set `controls` keys (`user:<id>:enabled`, `model:<name>:enabled`, `global:summarize:enabled`); changes are audited with before/after values.

### 7.4 Versioned prompts

- Prompts are **immutable**: editing creates a new version.
- A run stores `prompt_id`; the template's `body_sha256` is included in the audit payload.
- Exactly one version per name is active at a time; activation is an audited admin action.

### 7.5 Approval workflow

Policy outcome `flag` sets the document to `pending_approval`. An admin approves or denies with a required reason. Both outcomes are audited, and the run cannot start until approved.

### 7.6 Retention

`DELETE /documents/{id}/content` removes `document_contents.text`, sets `status='content_deleted'`, and nulls `run_steps.output_text` and stored quotes. Hashes, metadata, policy decisions, and audit events remain. Log `document.content_deleted`.

---

## 8. Auditing: Hash-Chained Log

### 8.1 What is logged

| Category | Actions |
|---|---|
| Auth | `auth.login.success`, `auth.login.failure`, `auth.logout` |
| Documents | `document.uploaded`, `document.validated`, `document.approved`, `document.denied`, `document.content_deleted` |
| Policy | `policy.decision` (one per check) |
| LLM | `llm.call.started`, `llm.call.succeeded`, `llm.call.failed`, `llm.call.retried`, `llm.rate_limited` |
| Runs | `run.created`, `run.completed`, `run.failed`, `run.blocked` |
| Views | `run.viewed`, `audit.viewed`, `audit.verified` |
| Admin | `prompt.created`, `prompt.activated`, `control.changed`, `user.role_changed` |
| Integrity | `audit.anchor.published` |

### 8.2 Payload rule

Payloads hold **metadata and hashes only**: document SHA-256, byte counts, model name, token counts, decision reasons. **Never** raw document text, passwords, or API keys. This keeps the log safe to retain after content deletion.

### 8.3 Hash specification

```
payload_json   = canonical JSON of the payload   (sorted keys, no whitespace, UTF-8)
payload_sha256 = SHA256(payload_json)

record_string  = canonical JSON of:
  { seq, ts, actor_id, actor_role, action, entity_type, entity_id,
    request_id, trace_id, payload_sha256, prev_hash }

hash = SHA256(record_string)
```

- **Genesis:** `prev_hash = "0" * 64` for `seq = 1`.
- **Timestamps:** UTC ISO-8601 with fixed precision; stored as text so serialization is stable.
- **Canonicalization** lives in one function shared by writer and verifier.
- **Store exactly what you hash.** `ts` and `payload_json` are TEXT columns holding the canonical strings, so Postgres never re-normalizes them. Format `ts` with a fixed pattern such as `2026-10-01T12:34:56.123456Z`.

### 8.4 Append procedure (concurrency-safe)

```python
AUDIT_LOCK_KEY = 727001   # same key as the DB trigger

def append_event(session, *, actor, action, entity, payload, request_id, trace_id):
    # Serialize all writers for the rest of this transaction (released on commit/rollback)
    session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": AUDIT_LOCK_KEY})

    last = session.execute(
        text("SELECT seq, hash FROM audit_events ORDER BY seq DESC LIMIT 1")
    ).first()
    prev_hash = last.hash if last else "0" * 64
    seq = (last.seq + 1) if last else 1

    payload_json = canonical_json(payload)
    payload_sha256 = sha256_hex(payload_json)
    ts = utc_now_canonical()
    hash_ = compute_hash(seq, ts, actor, action, entity, request_id, trace_id,
                         payload_sha256, prev_hash)

    session.execute(INSERT_AUDIT_EVENT, {...})   # DB trigger re-checks continuity
```

- The advisory lock is held until the surrounding transaction ends, so two concurrent requests cannot both read the same "last" row and fork the chain.
- The audit insert runs in the **same transaction** as the business action (e.g. creating a run). Either both commit or neither does. If the audit write fails, the action fails.
- The `audit_chain_check` trigger (section 6.2) independently enforces `seq` and `prev_hash` continuity, so a buggy code path cannot corrupt the chain.
- Trade-off to document: a global lock serializes audit writes. That is fine at portfolio scale, and at larger scale you would batch or shard chains per tenant.

### 8.5 Verification

```python
def verify_chain(session) -> VerifyResult:
    prev = "0" * 64
    expected_seq = 1
    for row in stream_events_ordered_by_seq(session):
        if row.seq != expected_seq:                       return broken(row.seq, "sequence gap")
        if row.prev_hash != prev:                         return broken(row.seq, "prev_hash mismatch")
        if sha256(canonical(row.payload_json)) != row.payload_sha256:
                                                          return broken(row.seq, "payload altered")
        if compute_hash(row) != row.hash:                 return broken(row.seq, "hash mismatch")
        prev = row.hash
        expected_seq += 1
    return ok(head_seq=expected_seq - 1, head_hash=prev)
```

`GET /audit/verify` returns `{ok, checked, head_seq, head_hash}` or `{ok:false, first_broken_seq, reason}`. Support `?from_seq=&to_seq=` for ranges, and cache the last verified head to make repeat checks incremental. Read rows with a server-side cursor (`stream_results=True` / `yield_per=1000` in SQLAlchemy) so verification uses constant memory, and run it in a `REPEATABLE READ` read-only transaction so a consistent snapshot is checked while new events are being appended.

### 8.6 External anchoring

A scheduled script (`scripts/anchor_cron.py`, run via GitHub Actions cron or locally) writes `{seq, hash, timestamp}` to a public repo file or Gist and logs `audit.anchor.published`. Verification can optionally compare the current chain's hash at `seq` to the anchored value, which detects a full-chain rewrite that internal checks would miss.

---

## 9. Traceability: Runs, Lineage, Citations

### 9.1 Run record

Every summary stores: document SHA-256, `input_sha256` (post-redaction text actually sent), provider, model, params, strategy, prompt template ID and hash, token counts, notional cost, latency, `trace_id`, and the audit event `seq` range it produced.

### 9.2 Lineage tree (map-reduce)

`run_steps` forms a DAG:

```
document ──► map step 1 (chars 0–12k)   ─┐
        ├──► map step 2 (chars 11.5k–24k) ├──► reduce step ──► final summary
        └──► map step N                  ─┘
```

Each step stores its char offsets, input hash, output, token usage, retry count, and `parent_step_ids`. The UI renders this as an expandable tree so an auditor can click from the final summary down to the exact chunk and output that fed it.

### 9.3 Source-grounded citations

The structured output schema:

```json
{
  "title": "string",
  "summary": "string",
  "key_points": [
    { "point": "string", "quote": "exact substring from the source" }
  ],
  "action_items": ["string"]
}
```

**Verification algorithm** (`pipeline/citations.py`):

1. Normalize whitespace and Unicode (NFKC) in both the source and the quote.
2. Search for the quote as an exact substring; record `char_start` and `char_end` in original coordinates.
3. If not found, optionally try a fuzzy match above a strict threshold (e.g. 0.95) and label it `approximate`.
4. Store `verified = 1/0`. Unverified points are flagged in the UI and counted in run metrics.

Run-level metric: **citation verification rate** (verified / total). This is a concrete, checkable form of traceability that is not "trust the model".

### 9.4 Run comparison

`GET /runs/{a}/diff/{b}` returns parameter differences (model, prompt version, effort), summary text diff, and citation-rate delta, rendered side by side.

### 9.5 Replay semantics

"Replay" means re-running with the **recorded inputs and parameters**, producing a **new run** linked to the original (`replay_of`). It does not promise identical output; the original output is the record of truth.

---

## 10. Summarization Pipeline

### 10.1 Ingest

- Accept `.txt` and `.md` only; check extension and content sniffing.
- Detect encoding with `charset-normalizer`; decode to UTF-8; reject if confidence is too low.
- Normalize line endings; compute SHA-256 of the normalized text.

### 10.2 Strategy selection

```
est_tokens = estimate_tokens(text) + prompt_overhead

if est_tokens <= SINGLE_CALL_LIMIT:      # e.g. 24k, conservative for free-tier TPM limits
    strategy = "single"
else:
    strategy = "map_reduce"
```

The threshold is a config value and is recorded in the run so decisions are explainable. Document why it is far below the model's ~128k context window (provider rate limits, latency, and quality).

### 10.3 Chunking

- Target ~3,000 tokens per chunk with ~200 tokens overlap.
- Split on paragraph boundaries, then sentences, then hard-split only as a last resort.
- Store exact char offsets so citations and lineage map back to the source.
- Property-based tests: chunks cover the whole text, overlap is respected, and offsets slice back to the chunk text.

### 10.4 Map-reduce

1. **Map:** summarize each chunk (bounded concurrency, e.g. 2, to respect free-tier limits), asking for key points *with quotes*.
2. **Reduce:** combine chunk summaries into the final structured summary. If the combined text is still too large, reduce hierarchically.
3. **Citation carry-through:** quotes come from the map outputs and are verified against the original source, not the intermediate summaries.

### 10.5 Reliability

- Retry with exponential backoff and jitter on 429/5xx; log `llm.rate_limited` and `llm.call.retried`.
- Per-call timeout; per-run overall timeout.
- Validate output with Pydantic; on failure, one repair retry with the validation error appended, then fail the run with a clear reason.
- Run status transitions are explicit and audited.

### 10.6 Controls exposed to users

Length (short / medium / long), style (bullets / executive / plain-language), and reasoning effort (low / medium), all constrained by the policy allowlist.

---

## 11. LLM Provider Abstraction

```python
class LLMProvider(Protocol):
    name: str
    async def complete(self, *, system: str, user: str, params: LLMParams) -> LLMResult: ...

@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model: str
    raw_finish_reason: str
```

Implementations:

- `OpenAICompatProvider(base_url, api_key, model)` covers Groq, OpenRouter, and Ollama.
- `MockProvider` returns deterministic output, including quotes lifted from the input, and can be configured to simulate 429s, timeouts, malformed JSON, and hallucinated quotes.

Provider and model are chosen from the allowlist and recorded per run. Swapping providers is a config change, not a code change. Never store reasoning traces; store only the final answer.

---

## 12. API Specification

All endpoints require authentication except login. Errors use a consistent envelope with a `request_id`.

### Auth
| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Start session |
| POST | `/auth/logout` | End session |

### Documents
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/documents` | user, admin | Upload and validate; triggers policy checks |
| GET | `/documents` | user (own), admin/auditor (all) | List |
| GET | `/documents/{id}` | owner, admin, auditor | Metadata and policy decisions |
| DELETE | `/documents/{id}/content` | owner, admin | Retention deletion |

### Runs
| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/documents/{id}/runs` | user, admin | Create a run (model, prompt, params) |
| GET | `/runs/{id}` | owner, admin, auditor | Result and metadata |
| GET | `/runs/{id}/lineage` | owner, admin, auditor | Step tree |
| GET | `/runs/{id}/citations` | owner, admin, auditor | Quotes and verification |
| GET | `/runs/{a}/diff/{b}` | admin, auditor | Comparison |
| POST | `/runs/{id}/replay` | owner, admin | New run from recorded inputs |

### Audit
| Method | Path | Roles | Description |
|---|---|---|---|
| GET | `/audit/events` | admin, auditor | Filter by actor, action, entity, time, trace ID |
| GET | `/audit/verify` | admin, auditor | Verify chain (optional range) |
| GET | `/audit/export` | auditor | JSONL export with head hash |
| GET | `/audit/trace/{trace_id}` | admin, auditor | All events for one request |

### Admin
| Method | Path | Description |
|---|---|---|
| GET/POST | `/admin/prompts` | List / create prompt versions |
| POST | `/admin/prompts/{id}/activate` | Activate a version |
| GET/POST | `/admin/controls` | Kill switches and allowlists |
| GET | `/admin/approvals` | Pending documents |
| POST | `/admin/approvals/{document_id}` | Approve/deny with reason |
| GET/POST | `/admin/users` | Manage users and roles |
| GET | `/admin/usage` | Token usage per user |

---

## 13. UI Plan

Server-rendered pages with HTMX partials:

1. **Login**
2. **Upload and summarize:** file picker, model/style/length options, live policy result panel.
3. **Run detail:** summary, key points with verified/unverified badges, metadata drawer (model, prompt version, tokens, trace ID).
4. **Lineage view:** expandable tree from final summary to chunks.
5. **Auditor console** (the showpiece):
   - Search the event log by actor, action, entity, or trace ID.
   - "Verify chain" button with a clear pass/fail banner and the broken sequence number when it fails.
   - Per-run **evidence pack**: lineage, policy decisions, prompt version and hash, citations, and the related audit events.
6. **Admin:** prompts, controls, approvals, users, usage.
7. **Run diff** view.

---

## 14. Observability

- **OpenTelemetry:** one trace per HTTP request, child spans for policy checks, each LLM call, and DB writes. The `trace_id` is stored in `runs`, `audit_events`, and shown in the UI.
- **Structured logs** (JSON) with `request_id` and `trace_id`; no document text.
- **Metrics** (simple counters/histograms exposed at `/metrics` or logged): run duration, tokens per run, policy denials by check, retry counts, citation verification rate.
- Exporters: console/file by default; optional Jaeger via docker compose.

---

## 15. Security and Privacy

- Passwords hashed with argon2; login throttling; secure, HTTP-only, SameSite cookies; CSRF protection on form posts.
- Secrets only via environment variables; `.env` is git-ignored; `.env.example` is committed.
- Upload limits enforced at the reverse proxy/app level; no file is ever executed or served back raw.
- Output is HTML-escaped; Jinja autoescape on; strict `Content-Security-Policy`.
- **Prompt-injection awareness:** treat document text as untrusted data; the system prompt states that document content is data, not instructions; policy and RBAC decisions never depend on model output.
- **Privacy notice** in the UI: text is sent to the configured provider. Free tiers may log prompts, so demos use public-domain texts only.
- Least privilege: the app DB role can INSERT to `audit_events` but not UPDATE or DELETE (Postgres).

---

## 16. Testing Strategy

| Layer | What to test |
|---|---|
| Unit | Canonical JSON, hash computation, each policy check, quota math, chunker, token estimator, citation matcher |
| Property-based (hypothesis) | Chunks reassemble to the source; offsets are valid; canonicalization is stable under key order |
| Integration | Full upload → policy → run → audit path with the mock provider |
| Audit integrity | Tamper with a payload, a `prev_hash`, a deleted row, and a reordered row; verifier must report the first broken `seq` each time |
| Concurrency | Many parallel appends produce a single unforked chain |
| Trigger tests | Direct `UPDATE`/`DELETE`/`TRUNCATE` on `audit_events` fails; inserting a row with a wrong `prev_hash` or skipped `seq` is rejected by `audit_chain_check` |
| Privilege tests | Connected as `auditsum_app`, `UPDATE`/`DELETE` on `audit_events` raises a permission error |
| Test database | Run integration tests against a **separate** Postgres database (or throwaway schema per test session, e.g. via a Docker container), never your main data |
| RBAC | Table-driven matrix test for every endpoint × role; unknown endpoints denied by default |
| Failure injection | Mock 429s, timeouts, malformed JSON, hallucinated quotes; verify retries, audit events, and status transitions |
| Retention | After content deletion, no raw text remains anywhere, but audit and hashes do |

Target: >85% coverage on `audit/`, `policy/`, `pipeline/`. CI runs ruff, mypy, and pytest on every push.

---

## 17. Evaluation Harness

`eval/run_eval.py` measures summary quality instead of eyeballing it.

- **Corpus:** 5–10 public-domain texts of varying length (short essay to a full novel) so both strategies are exercised.
- **Automated metrics:** compression ratio, format validity, citation verification rate, key-point coverage against a small hand-written list of expected points per text.
- **Optional LLM judge:** rubric in `rubric.yaml` (faithfulness, coverage, concision, 1–5); record judge model and prompt version.
- **Comparisons:** `gpt-oss-120b` vs `gpt-oss-20b`, or prompt v1 vs v2; outputs a table of quality, latency, tokens, and notional cost.
- Results are written to a markdown report and referenced in this README.

---

## 18. Free-Tier Constraints

| Constraint | Mitigation |
|---|---|
| Provider rate limits (RPM/TPM/daily) | Bounded concurrency, backoff with jitter, audited retries, conservative single-call threshold |
| Limits change without notice | Mock provider for dev/CI; check provider docs before demo |
| Free models may log prompts | Public-domain texts only; state this in the UI and README |
| Postgres storage cap / idle suspension (if your instance is a free tier) | Keep payloads metadata-only; retry the first connection on cold start; use `pool_pre_ping=True`; prune old demo data |
| Cold starts | Note in the README; keep a recorded demo as a fallback |
| No real spend | Track **notional cost** from published per-token prices; budgets enforce on tokens |
| Public demo abuse | Per-user and per-IP rate limits, small size cap, pre-seeded demo accounts only, global daily token cap with mock fallback (section 19.4) |

---

## 19. Hosting and Public Demo

The goal: a hiring manager clicks a link, is inside a working, pre-populated app within seconds, and can reach the "verify chain, then tamper, then detect" moment without creating an account or spending anything.

### 19.1 Hosting architecture

```mermaid
flowchart LR
    V[Visitor] -->|HTTPS| H[Hugging Face Space: Docker, port 7860]
    H -->|TLS, app role| PG[(PostgreSQL: hosted, internet-reachable)]
    H -->|API key in secret| L[Free-tier LLM provider]
    H -.fallback.-> M[Mock provider]
    GH[GitHub repo + Actions] -->|tests, then deploy| H
    GH -->|Alembic migrations, owner role| PG
    GH -.hourly/daily anchor.-> A[Public anchor file]
```

### 19.2 Where to host (free)

| Option | Pros | Cons |
|---|---|---|
| **Hugging Face Spaces (Docker SDK), recommended** | Free CPU tier (2 vCPU, 16 GB), HTTPS included, deploy by git push, secrets support, free Spaces sleep after ~48 hours idle rather than minutes | Disk is not persistent on the free tier (fine, since data lives in Postgres); container must listen on port 7860; a public "AI demo" platform, which suits this project |
| Render (free web service) | Simple GitHub deploys | Spins down after 15 minutes idle and takes about a minute to wake, so a recruiter's first click hangs; filesystem is ephemeral; free instance-hour cap per month |

Free-tier terms change, so re-check both providers' current docs before you deploy. Static hosts (GitHub Pages, Netlify) do not fit because the app needs a backend.

### 19.3 Database must be reachable from the internet

A hosted app cannot reach a Postgres running only on your laptop. Your instance needs a public, TLS-enabled endpoint (for example a free tier at Neon or Supabase, or a VPS). Requirements:

- Connect with `sslmode=require` (or `verify-full` with the provider's CA).
- Use a **dedicated database or schema for the demo**, separate from anything else you own.
- Confirm the provider allows `CREATE ROLE` (for `auditsum_app`) and the advisory locks and triggers used here. If it does not allow roles, keep the triggers and document role separation as a recommendation.
- Use `pool_pre_ping=True` and a small pool (2 to 5 connections) to respect free-tier connection limits and handle idle suspension.
- Check the storage cap; the metadata-only audit log is small, but documents and step outputs add up.

### 19.4 Public-demo safety (the part reviewers will probe)

A public URL with your API key behind it is an abuse target. Layer these controls:

| Risk | Control |
|---|---|
| Strangers creating accounts | **No open signup.** Three pre-seeded demo accounts (`demo-user`, `demo-admin`, `demo-auditor`) with a one-click role switcher on the landing page; credentials shown on the page |
| Draining the free LLM quota | Per-IP and per-user rate limits; a **global daily token cap** (`DEMO_DAILY_TOKEN_CAP`). When reached, the circuit breaker either denies new runs with a clear message or **falls back to the mock provider** with a visible "simulated output" banner, so the demo never shows a raw error |
| Large or hostile uploads | Demo size cap (e.g. 50 KB), `.txt`/`.md` only, plus one-click **sample texts** (public domain) so visitors don't need to upload anything |
| Real personal data | Banner: "Demo only. Do not upload real or confidential data." Sample texts include a fake email address to trigger the PII policy |
| Admin abuse from the shared admin account | Demo admin can change prompts, controls, and kill switches, but cannot alter roles or credentials, and a rate limit applies to admin actions |
| Leaked keys | Provider key only in Space **Secrets**; never in the repo, image, logs, or client code; spending/usage limit set at the provider; rotate if exposed |
| Rate limiting behind a proxy | Trust only the host's forwarded-IP header, and only from the known proxy, otherwise IP limits can be spoofed |
| Log growth | Global cap on total audit events per day for anonymous demo traffic; alert in the admin usage page |

### 19.5 Recruiter experience

- **Landing page** with three buttons: *Try as User*, *Try as Admin*, *Try as Auditor*, and a **guided tour** (a short checklist that walks through: upload sample → see policy decision → run → open lineage → verify chain → tamper → verify again).
- **Tamper button for the demo only:** because visitors cannot run `tamper_demo.py`, the hosted demo exposes a clearly labeled *Simulate tampering* action on a **separate sandbox chain** (a second, disposable audit table or schema with the same triggers disabled) so the real demo log stays intact. The auditor console then shows the verifier catching the edit and naming the broken `seq`. Reset the sandbox chain on demand.
- **`/healthz`** (no auth, no DB writes) for uptime checks and **`/version`** showing the git SHA and migration revision.
- **Status banner** showing the active provider (real vs. mock) and remaining daily budget.
- **Cold-start handling:** a friendly loading state, plus a **60 to 90 second demo video/GIF** at the top of the GitHub README as a fallback if the Space is asleep or the free LLM tier is exhausted. Wake the Space before sending applications; an optional scheduled GitHub Actions ping (once or twice a day) can keep a sleeping free Space warm, but treat it as a convenience, not a guarantee.

### 19.6 Deployment pipeline (GitHub Actions)

1. **On every push:** ruff, mypy, pytest (mock provider, throwaway Postgres service container).
2. **On merge to `main`:**
   - Run `alembic upgrade head` against the demo database using the **owner** credentials stored as a GitHub Actions secret.
   - Push the repository to the Hugging Face Space remote using an HF access token stored as a GitHub secret.
3. **Runtime container** receives only the **app-role** `DATABASE_URL`, the LLM key, and demo settings via Space Secrets/Variables. Migrations never run inside the container, so the owner credentials are not present where the app runs, which preserves the privilege separation from section 6.2.

Space requirements:
- Root `README.md` of the Space repo needs YAML front matter (`sdk: docker`, `app_port: 7860`). To keep your GitHub README clean, have the deploy workflow prepend the front matter to a copy of the README before pushing to the Space.
- The `Dockerfile` binds to `0.0.0.0:7860`, runs as a non-root user, and starts uvicorn directly.
- **Embedding caveat:** Spaces can display the app inside a frame on the huggingface.co page, where session cookies may be blocked as third-party. Put the **direct app URL** (the `*.hf.space` address) on your resume and README, and set cookies `Secure; HttpOnly; SameSite=Lax` (or `None` only if you deliberately support embedding).

### 19.7 Demo configuration

```
DATABASE_URL=postgresql+psycopg://auditsum_app:***@host/db?sslmode=require   # app role only
LLM_PROVIDER=openai_compat            # or mock
LLM_BASE_URL=...                      # provider endpoint
LLM_API_KEY=...                       # Space secret
LLM_MODEL=gpt-oss-120b
DEMO_MODE=true
DEMO_DAILY_TOKEN_CAP=200000
DEMO_MAX_UPLOAD_BYTES=51200
DEMO_FALLBACK_TO_MOCK=true
RATE_LIMIT_PER_MINUTE=6
TRUSTED_PROXY_HEADER=X-Forwarded-For
SESSION_SECRET=...                    # Space secret
```

### 19.8 Data lifecycle on a public demo

The audit log is append-only by design, so you cannot simply "clear the demo". Plan for it:

- Run the demo in its **own schema or database**. Periodic housekeeping (for example monthly) is a documented owner-level maintenance step, `scripts/reset_demo.py`: drop and recreate the demo schema through migrations, reseed the accounts, prompt versions, and sample runs, and publish a new anchor entry noting the reset epoch.
- State this openly in the README: the reset is an out-of-band administrative action, not something the application role can do, which is exactly the separation the project demonstrates.
- Content retention still applies: uploaded demo text can be auto-deleted after 24 hours using the same content-deletion path (audit metadata is kept).

### 19.9 Portfolio packaging

The top of the public GitHub README should let a reviewer decide in 30 seconds:

1. One-sentence pitch and a **live demo link** with the demo credentials.
2. The 60 to 90 second GIF/video.
3. A "Try it in 2 minutes" checklist matching the guided tour.
4. Architecture diagram and a short "design decisions" section (why hash chaining, why TEXT-canonical hashing, why privilege separation, why map-reduce thresholds).
5. Known limitations (section 22), stated honestly.
6. Links to the evaluation report and the test coverage badge (CI badge for the pipeline).
7. A one-paragraph note on how the free-tier constraints shaped the design, which shows engineering judgment rather than hiding limitations.

## 20. Milestones

Roughly 3–4 weeks part-time including hosting for the core project (Milestones 1–8). Milestone 9 (RAG) is optional and adds about a week on top; do it only if the core is solid and you have time left.

**Milestone 1: Foundations (days 1–3)**
- Repo, Docker, CI, config, SQLAlchemy models and Alembic migrations against your Postgres
- `db/roles.sql`: create the `auditsum_app` role and grants; app connects as that role, migrations as the owner
- Separate test database and pytest fixtures
- Auth and RBAC dependency with the permission matrix and its test
- Mock LLM provider

**Milestone 2: Audit core (days 4–6)** *(the centerpiece; build before other features)*
- Canonicalization, `append_event` with `pg_advisory_xact_lock`, immutability and chain-check triggers
- `verify_chain` and `/audit/verify`
- Tamper, concurrency, and trigger tests; `tamper_demo.py`

**Milestone 3: Control (days 7–9)**
- Policy engine and checks (size, model, encoding, PII)
- Quotas, controls/kill switch, versioned prompts, approval flow
- Audit events for every decision

**Milestone 4: Pipeline and traceability (days 10–14)**
- Ingest, token estimation, chunker (with property tests)
- Single-call and map-reduce with `run_steps` lineage
- Structured output validation, retries, backoff
- Citation verification

**Milestone 5: Real provider (days 15–16)**
- OpenAI-compatible provider for `gpt-oss-120b` on a free tier; optional Ollama
- Failure-injection tests against the mock; smoke test against the real API

**Milestone 6: UI and observability (days 17–19)**
- Upload, run detail, lineage tree, auditor console, admin pages, run diff
- OpenTelemetry tracing and metrics

**Milestone 7: Hosting (days 20–23)**
- Dockerfile for Hugging Face Spaces (port 7860, non-root), Space front-matter step in the deploy workflow
- Demo mode: seeded accounts, role switcher, sample texts, global token cap and circuit breaker, mock fallback, banner
- Sandbox tamper chain for the hosted tamper demo
- `/healthz`, `/version`, CI deploy workflow (migrations from Actions with the owner role, container with the app role only)
- Smoke test the live URL end to end, including a cold start and a rate-limit fallback

**Milestone 9 (optional stretch): RAG Q&A (days 26–31)**
- Only start this after Milestones 1–7 are done and stable; see section 24 for full design
- `chunks` table with embeddings (pgvector, or array + Python cosine similarity if the extension isn't available)
- Local embedding model (`sentence-transformers` or Ollama) so no API cost and no text leaves the machine for embedding
- Embed on document ingest; store alongside existing `run_steps`-style records for traceability
- `POST /documents/{id}/questions` endpoint: retrieve top-k chunks, answer with quotes, verify quotes with the existing citation module
- Every question is its own `runs` row (`strategy='rag_qa'`) with retrieved chunk IDs and similarity scores recorded, same policy/RBAC/audit treatment as summarization
- Q&A UI panel on the run detail page; retrieved-chunks panel showing what fed the answer
- Extend the evaluation harness with a Q&A accuracy check
- Extend the hosted demo cautiously: RAG adds another LLM call per question, so it shares the same daily token cap and circuit breaker (section 19.4)

**Milestone 10: Polish (days 32–33)**
- Evaluation harness and report
- External hash anchoring
- Architecture diagram, demo GIF/video, final README, deployment

---

## 21. Demo Script

> On the hosted demo, the same flow runs through the role switcher and guided tour (section 19.5). Step 8 uses the sandbox chain instead of `tamper_demo.py`.

1. Log in as `user`; upload a public-domain text with an embedded fake email address. The policy panel shows a PII **redact** decision.
2. Run a summary; watch status and citations populate. Open the **lineage tree** for a long text (map-reduce).
3. Show a **hallucinated quote** (from the mock provider) flagged as unverified.
4. Log in as `admin`; create prompt v2, activate it, rerun, and open the **run diff**.
5. Flip the model **kill switch** and show the next run blocked, with the policy decision and audit event.
6. Log in as `auditor`; open the **evidence pack** for a run: lineage, policy decisions, prompt hash, citations, linked events.
7. Click **Verify chain**: pass.
8. In a terminal, run `scripts/tamper_demo.py`. Acting as the table owner (a simulated rogue DBA), it runs `ALTER TABLE audit_events DISABLE TRIGGER USER;`, edits one audit row, then re-enables the triggers. (First show that the same `UPDATE` is rejected when attempted as `auditsum_app`.) Click **Verify chain** again: it fails and names the exact broken `seq` and reason.
9. Show the externally anchored hash in the public repo to explain how a full-chain rewrite would be caught.

---

## 22. Known Limitations

- **Tamper-evident, not tamper-proof.** Anyone with full database and code access could recompute the entire chain. External anchoring mitigates this but does not eliminate it; production systems would add write-once storage or a trusted timestamping service.
- **LLM non-determinism.** Replays produce new outputs; the stored original is the record.
- **PII detection is heuristic** and will miss some cases and flag some false positives.
- **Quote verification proves the quote exists, not that the point is faithful to it.** Faithfulness is only sampled via the optional LLM judge.
- **Free-tier availability and limits** can change and affect the live demo. The demo degrades gracefully to the mock provider, and the README carries a recorded walkthrough.
- **The public demo uses shared accounts and a sandbox tamper chain.** The real chain is never tampered with in front of visitors; the reset procedure for the demo schema is an owner-level administrative action.
- **RAG (section 24) is an optional stretch goal, not required for the core project to be complete.** Ship and polish the core governance features first.
- **Text files only.** PDF/OCR is a planned extension.
- **Notional cost** is an estimate from published prices, not a bill.

---

## 23. Definition of Done

- [ ] Every endpoint has an explicit RBAC permission and a test proving denial for other roles
- [ ] Every state-changing action writes an audit event in the same transaction
- [ ] `UPDATE`/`DELETE` on `audit_events` fails at the database level
- [ ] `/audit/verify` detects payload edits, deleted rows, reordered rows, and altered hashes, and reports the first broken `seq`
- [ ] Concurrent appends never fork the chain
- [ ] No raw document text appears in the audit log, application logs, or traces
- [ ] Any run can be traced to: document hash, prompt version and hash, model, params, per-step inputs/outputs, and citations
- [ ] Citation verification rate is computed and displayed for every run
- [ ] Content deletion removes text everywhere while preserving audit metadata
- [ ] Full pipeline passes CI using only the mock provider
- [ ] Evaluation report committed for at least two model/prompt configurations
- [ ] README includes architecture diagram, demo video/GIF, trade-offs, and limitations
- [ ] The whole project runs with `docker compose up` at zero cost
- [ ] A public HTTPS URL serves the app; visitors reach a working state in under 30 seconds with no signup
- [ ] The container holds only the app-role DB credentials; migrations run from CI
- [ ] Global daily token cap and mock fallback verified by a test and a live check
- [ ] Hosted tamper demo detects the edit on the sandbox chain and names the broken `seq`
- [ ] README top section has the live link, demo credentials, walkthrough video/GIF, and quick tour


---

## 24. Optional Stretch: RAG Q&A (Milestone 9)

Build this **only after** Milestones 1–8 are solid. It is additive: it reuses the existing auth, RBAC, policy engine, hash-chained audit log, and citation verifier rather than introducing parallel systems. The point of including it at all is to add a second, distinct AI-engineering artifact (retrieval quality and grounding) alongside summarization, while keeping the governance story front and center: **every retrieval and every answer is audited and cited, exactly like a summary is.**

### 24.1 Why RAG fits the governance angle

A plain RAG demo answers "does retrieval work." This version answers a more interesting question: **can you prove which passages produced an answer, and catch it when the model claims something the retrieved text doesn't support?** That reuses section 9.3's citation verification almost unchanged, which is why this is a small addition rather than a second project.

### 24.2 Schema additions

```sql
-- Chunk-level embeddings for retrieval (separate from run_steps' map-reduce chunks,
-- though the chunking function itself, section 10.3, is reused)
CREATE TABLE document_chunks (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id   BIGINT NOT NULL REFERENCES documents(id),
  chunk_index   INTEGER NOT NULL,
  char_start    INTEGER NOT NULL,
  char_end      INTEGER NOT NULL,
  text_sha256   CHAR(64) NOT NULL,
  embedding     VECTOR(384),              -- pgvector; dimension matches the embedding model
  embedding_model TEXT NOT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (document_id, chunk_index)
);
CREATE INDEX document_chunks_embedding_idx
  ON document_chunks USING hnsw (embedding vector_cosine_ops);

-- Which chunks were retrieved for a given Q&A run, and how well they matched
CREATE TABLE retrieval_results (
  id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  run_id        BIGINT NOT NULL REFERENCES runs(id),
  chunk_id      BIGINT NOT NULL REFERENCES document_chunks(id),
  rank          INTEGER NOT NULL,
  similarity    REAL NOT NULL,
  used_in_answer BOOLEAN NOT NULL DEFAULT TRUE
);
```

- `runs.strategy` gains a third value: `'rag_qa'`.
- `runs.result_json` for a Q&A run holds `{question, answer, key_points_with_quotes}`, validated the same way as a summary.
- If `pgvector` (`CREATE EXTENSION vector`) isn't available on your Neon project, store `embedding` as `REAL[]` and compute cosine similarity in Python at query time; at portfolio-scale document counts this is fast enough and avoids an extension dependency. Document whichever you pick and why.

### 24.3 Pipeline

1. **On ingest** (after the existing validation in section 10.1): chunk the document with the same chunker as section 10.3 (smaller target, e.g. ~500 tokens, no need for the map-reduce overlap logic), embed each chunk locally, store rows in `document_chunks`. Log `document.embedded`.
2. **On a question** (`POST /documents/{id}/questions`):
   - Policy engine runs first, same as summarization (size/model checks don't apply the same way, but the kill switch, PII scan of the *question*, and quota checks do).
   - Embed the question locally.
   - Retrieve top-k (e.g. k=5) chunks by cosine similarity; store them in `retrieval_results` with rank and score, before the LLM call, so retrieval is audited even if generation fails.
   - Call the LLM with the retrieved chunks as context, asking for an answer plus quotes per claim (same schema shape as section 9.3).
   - Verify each quote against the **original chunks actually retrieved**, not the whole document, so traceability is exact: an unverified quote means the model said something not present in what it was given.
   - Create the `runs` row (`strategy='rag_qa'`) and the usual `run_steps`/citations/audit events.

### 24.4 API additions

| Method | Path | Roles | Description |
|---|---|---|---|
| POST | `/documents/{id}/questions` | user, admin | Ask a question; returns a `run` of strategy `rag_qa` |
| GET | `/runs/{id}/retrieval` | owner, admin, auditor | Retrieved chunks, ranks, similarity scores, which were used |

### 24.5 UI additions

- A **Q&A box** on the document/run page, alongside the existing summarize action.
- A **retrieved-chunks panel** on the run detail view, showing exactly which passages (with offsets) were retrieved and their similarity scores, mirroring the lineage tree's "show your work" style from section 9.2.
- Unverified quotes in an answer get the same visual flag as in summaries (section 9.3).

### 24.6 Evaluation additions

Extend `eval/run_eval.py` (section 17) with a small Q&A test set per corpus document: hand-written questions with expected answers or expected source passages. Metrics: retrieval hit rate (did the right chunk get retrieved in the top-k), citation verification rate, and optionally an LLM-judge faithfulness score, reusing the existing rubric infrastructure.

### 24.7 Cost and hosting impact

Each question is one embedding call (free, local) plus one LLM call, so it consumes the same daily token budget and circuit breaker as summarization (section 19.4). No new infrastructure is needed for hosting; `document_chunks` and `retrieval_results` live in the same Postgres database.

### 24.8 Milestone 9 checklist

- [ ] `document_chunks` and `retrieval_results` tables and migration
- [ ] Local embedding step wired into ingest, with a test using the mock provider's deterministic embeddings
- [ ] Retrieval function with a unit test (`hypothesis`-based: correct chunk ranks highest for an obvious match)
- [ ] `/documents/{id}/questions` endpoint with full policy/RBAC/audit treatment
- [ ] Citation verification reused unmodified against retrieved chunks
- [ ] Q&A UI panel and retrieved-chunks panel
- [ ] Eval harness extended with retrieval hit rate and citation rate for Q&A
- [ ] Demo token cap covers Q&A calls; smoke-tested on the hosted Space
