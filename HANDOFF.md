# HANDOFF — SupportPilot AI

_Last updated: 2026-10-25_

## Where the project stands

| Phase | Scope | Status |
| :--- | :--- | :--- |
| **Phase 1** | Foundation, auth, workspaces, roles | ✅ Verified (tests + build green) |
| **Phase 2** | Ticket management (models, API, inbox, detail, portal, seed, tests) | ✅ Delivered — one documented limitation (portal identity) |
| **Phase 3** | Knowledge base + RAG (ingestion, pgvector/SQLite vector store, retrieval, grounded chat, UI) | ✅ Delivered |
| **Phase 4** | AI classification, escalation rules, grounded reply drafts, triage UI | ✅ Delivered |
| **Phase 5** | Human approval (HITL core) | ✅ Complete (API + backend + 12 tests) |
| Phase 6 | Analytics + integrations | ⏳ Not started |
| Phase 7 | Production readiness | ⏳ Not started |

---

## Phase 4 — what is finished

### Data model & migration
- `tickets.ai_urgency_score` (float) and `tickets.ai_classification_json` (full classification payload for audit: provider/model, suggested fields, thresholds, escalation reasons).
- Index `ix_tickets_workspace_escalated` for the triage filter.
- Alembic revision `004_phase4_ai_triage`, applied to a fresh SQLite DB and to the local dev database.

### Classification (`app/ai/classifier.py`)
- `TicketClassification`: category, priority, sentiment, intent, confidence, summary, urgency score, `requested_human`, provider/model.
- `MockTicketClassifier` — deterministic keyword/phrase rules with weighted multi-word signals, a duplicate-charge/refund override, and sales/service intent rules. No network, no randomness.
- `LLMTicketClassifier` — one strict JSON completion from the workspace's configured provider, validated with Pydantic against the allowed categories/priorities/sentiments; malformed responses raise `ProviderError`. Customer input is sanitized and wrapped in `<customer_input>`.
- Vocabularies are asserted against `ticket_service` in tests so category/priority lists cannot drift.

### Escalation policy (`evaluate_escalation`)
A ticket is flagged for human review when any of these hold:
- urgency ≥ the workspace's `auto_escalate_urgency_threshold` (default `0.85`);
- intent is sensitive (refunds, duplicate charge, chargeback, data breach, security incident, legal threat, account deletion, human handoff);
- sentiment is `angry`;
- classification confidence < `AI_LOW_CONFIDENCE_THRESHOLD` (default `0.55`);
- the customer explicitly requested a human/supervisor.

`is_escalated` and `escalation_reason` are written on creation for both staff and portal tickets. Escalation is **sticky**: reclassification can add it, never silently clear it. Triage **never changes ticket status** and never sends messages — moving to `escalated` remains a human status decision. AI/provider failures during creation are logged and swallowed so ticket intake never breaks; an explicit reclassify surfaces `503`.

### API
| Method | Path | Role | Notes |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/tickets/{id}/classify?apply=false` | admin, agent | re-runs triage; `apply=true` writes the suggested category/priority |
| `POST` | `/api/tickets/{id}/suggested-reply` | admin, agent | grounded draft + citations; never saved or sent |
| `GET` | `/api/tickets?escalated=true` | admin, agent | escalation filter |

Creation (`POST /api/tickets` and `POST /api/portal/tickets`) now writes AI triage metadata automatically. Portal responses redact all AI internals (`ai_*`, urgency, escalation reasons, `is_escalated`) — customers only see customer-facing ticket data.

### Suggested replies
- Builds a query from the subject + the last three customer messages, retrieves workspace-scoped chunks through the Phase 3 retriever, and asks the provider for a reply grounded strictly in that context.
- Returns `draft`, citations (document/chunk/score/excerpt), threshold, top score and a note. Nothing is written to the thread.
- No evidence above the threshold → `grounded=false`, `draft=null`, no citations, with a note to reply manually or escalate.
- Mock mode wraps the extractive, cited answer in a greeting/sign-off so the demo draft reads like a reply while remaining non-fabricated.

### Frontend
- **Ticket detail**: an AI Triage card shows intent, sentiment, confidence, urgency, suggested category/priority and escalation reasons, with **Reclassify** and **Apply suggestion** actions (human-triggered only). The composer has **Draft with AI**, which inserts the grounded draft for editing and displays its source cards; nothing is auto-sent.
- **Ticket inbox**: new **Escalated only** filter alongside the existing AI summary/escalation indicators.
- Dashboard header reflects Phase 4.

### Tests
`cd backend && pytest -v` → **53 passed** (40 existing + 13 Phase 4).

New coverage in `tests/test_triage_phase4.py`:
- classification on creation, refund/duplicate-charge intent, staff escalation reasons, status staying `open`;
- non-sensitive inquiry not escalated; angry sentiment; human request; low confidence;
- workspace threshold changing escalation for the same ticket;
- classify without/with apply, RBAC (agent allowed, anonymous CSRF-blocked) and cross-workspace `404`;
- portal creation hides AI metadata while staff see it;
- grounded reply draft + citations with no message persisted, no-evidence path, agent access, cross-workspace `404`, unauthenticated `401`;
- provider failure tolerated on creation and surfaced as `503` on explicit reclassify;
- deterministic mock classifier, vocabulary parity, strict LLM JSON parsing and sanitized fallbacks.

Manual HTTP run on a fresh migrated + seeded SQLite DB: ticket creation → `is_escalated=true`, `duplicate_charge_refund`, urgency `0.8`; escalation list; grounded draft with 2 citations; `classify?apply=true` → category `refunds`, priority `high`; portal creation hides AI metadata while staff still see it.

### Frontend build
`cd frontend && npm run build` → compiled successfully (next build includes `/tickets` and `/tickets/[id]`), `npx tsc --noEmit` clean.

---

## Phase 5 — What is finished

### Data model
- `action_proposals` table (schema: workspace_id, ticket_id, action_type, action_params_json, rationale, ai_confidence, status, expires_at, created_at, reviewed_by_user_id, reviewed_at, reviewer_note, idempotency_key, executed_at, execution_result_json).
- `audit_logs` table (schema: workspace_id, event_category, event_type, actor_user_id, actor_email, target_ticket_id, target_proposal_id, details_json, ip_address, user_agent, created_at).
- Alembic migration `005_phase5_hitl_approvals` creates both tables and adds `execution_result_json` column to `action_proposals`.

### API endpoints
| Method | Path | Role | Notes |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/proposals` | admin, agent | Create a pending consequential-action proposal. Requires `action_type`, `params`, `rationale`. Auto-sets status to `pending_approval` on the ticket. |
| `GET` | `/api/proposals` | admin, agent | List proposals with pagination and filtering (status, action_type). Expired pending proposals are swept first. |
| `GET` | `/api/proposals/{id}` | admin, agent | Single proposal with computed approval policy and ticket subject. |
| `POST` | `/api/proposals/{id}/approve` | admin, agent | Executes an approved proposal exactly once. Idempotency key guards against double execution. Re-validation of role limits (e.g. refunds above $250 require an Admin). Emits `proposal_approved` / `proposal_executed` audit events. |
| `POST` | `/api/proposals/{id}/reject` | admin, agent | Rejects a pending proposal. Writes `proposal_rejected` audit event. Ticket returns to `in_progress` status. |
| `GET` | `/api/audit` | admin | Read-only, workspace-scoped immutable audit trail. Filters by category, event_type, ticket_id, proposal_id. No create/update/delete verbs — rows are append-only. |

### Services
- `app/services/approval_service.py` — atomic pending→decided transition, idempotency key enforcement, role re-validation via `policy_engine.py`, audit writes via `audit_service.py`.
- `app/services/policy_engine.py` — strict per-action parameter validation (forbids unknown fields), server-side policy limits (agent vs Admin), deterministic mock executor via `action_executor.py`.
- `app/ai/tools.py` — AI-side tool boundary: every function only creates a pending proposal; zero execution capability. All functions auto-commit to DB.

### Tests
`cd backend && pytest -v` → **65 passed** (53 Phase 4 + 12 Phase 5).

New coverage in `tests/test_approvals_phase5.py`:
- proposal creation is pending and audited, unknown params are rejected 422, agent vs Admin role limits are enforced, proposals are idempotent on replay, rejection prevents execution, expired proposals cannot be approved, duplicate idempotency keys across proposals are rejected, cross-workspace proposals are invisible, authenticated-only API surface, closed tickets cannot gain proposals, AI tools only create pending proposals without execution.

### Frontend
- **Approval UI**: placeholder at `/approvals` showing HITL architecture safeguards. TODO for Phase 6.
- **Audit log viewer**: admin-accessible (placeholder) showing immutable append-only audit entries.

---

## Phase 4 demo flow

1. Sign in as `admin@acme.com` → **Ticket Inbox** → create a ticket describing a duplicate charge and an angry follow-up.
2. Open it: the AI Triage card shows intent, sentiment, urgency, suggested category/priority and escalation reasons; status remains `open`.
3. Use **Draft with AI** → a grounded draft appears in the composer with source cards. Edit and send only if you choose.
4. Use **Apply suggestion** to adopt the AI category/priority (a human action), or **Reclassify** after adding knowledge.
5. Check the **Escalated only** filter in the inbox.

---

## How to run

```bash
# Backend (local, SQLite)
cd backend
source .venv/Scripts/activate        # Windows; use .venv/bin/activate on Linux/macOS
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev                          # http://localhost:3000

# Tests
cd backend && pytest -v
```

Demo logins (password `SupportPilot2026!`): `admin@acme.com` (admin), `agent@acme.com` (support agent), `admin@beta.com` (other workspace).

Customer portal: `http://localhost:3000/portal` — seeded customer email `customer@acme.com`.

Customer AI chat: `http://localhost:3000/portal/chat?email=customer@acme.com`.

---

## Known limitations / partial work (honest status)

1. **Customer portal and chat identity is email-scoped, not authenticated** (ADR-007). Production requires authenticated customers.
2. **The public chat has no rate limiting or abuse controls** (Phase 7).
3. **Mock classification is keyword-based.** It is deterministic and tuned for the seeded corpus, but real semantic accuracy needs `LLM_PROVIDER=openai|gemini`. LLM classification requires a JSON-returning model and surfaces `503` on malformed output.
4. **Auto-escalation is a flag, not a status change.** Agents still move tickets to `escalated`; this keeps intake and lifecycle decisions human-controlled. The inbox filter exposes flagged tickets.
5. **Reclassification is sticky**: adding evidence that a ticket is calm will not clear `is_escalated` or the stored reasons. Clearing requires a future explicit action.
6. **Suggested drafts are drafts.** Mock drafts are extractive and read like policy text; real providers produce more conversational output. Nothing is auto-sent, by design.
7. **PostgreSQL + pgvector path and Docker Compose remain unexecuted here** (no Docker binary). SQLite was verified end to end.
8. **No OCR** for scanned PDFs; **only extracted text** is retained (no original-file download).
9. **SQLite retrieval scans up to `RETRIEVAL_SCAN_LIMIT` (2000) chunks in Python**; production relies on the pgvector index.
10. **Audit logging for ticket/triage/knowledge events is not written yet.** `audit_logs` exists; Phase 5 owns audit writes.
11. **No streaming chat / conversation memory / notifications**; Recharts still absent until Phase 6 (ADR-008).
12. **Frontend `npm run lint` was not run** (Next lint prompts for config); build and TypeScript checks pass.

---

## Phase 5 demo flow

1. Sign in as `admin@acme.com` → **Ticket Inbox** → create a ticket describing a duplicate charge.
2. Sign in as `agent@acme.com` → open the ticket → **AI Triage** card shows intent, sentiment, suggested refund.
3. Agent uses **Propose Refund** → creates a pending proposal (amount $120, reason verified).
4. Agent clicks **Approve** → role validation passes (agent can approve up to $250); proposal approved and executed; refund receipt returned.
5. Audit event `proposal_approved` / `proposal_executed` logged immutably.
6. Admin clicks **Approve** on a refund above $250 → role validation requires Admin; proceeds.
7. Expired proposals are swept; attempts to approve expired proposals return 409.
8. All actions are visible in the read-only `/api/audit` endpoint.
9. Rejected proposals stay `rejected` with `execution_result: null`; ticket status returns to `in_progress`.