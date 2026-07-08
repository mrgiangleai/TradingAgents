# Session Log

---

## Phase 1.1

Done:
- Created Python virtual environment
- Installed dependencies
- Verified CLI works

Test:
- ✅ tradingagents --help

Commit:
- docs: record phase 1.1 setup

Next:
- Phase 1.2 — Run baseline demo

---

## Phase 1.2

Done:
- Created `.env` from `.env.example` (gitignored, not committed).
- Tried OpenAI (gpt-5.4-nano) first — key hit `insufficient_quota` (429), no billing on account.
- Switched to Google (gemini-3.1-flash-lite) — ran full pipeline successfully on AAPL / 2026-07-08 with all 4 default analysts.
- Recorded baseline (time, LLM calls, tokens, decision) in `TEST_PLAN.md`.

Test:
- ✅ Final decision produced: Overweight (Buy, 3% position).
- ✅ `test_memory.md` got a new pending entry.
- ✅ Real memory path (`trading_memory.md`) confirmed untouched (file still doesn't exist).

Memory path used this session:
- `~/.tradingagents/memory/test_memory.md` (via `TRADINGAGENTS_MEMORY_LOG_PATH`)

Commit:
- docs: record baseline demo run

Next:
- Phase 2.1 — Audit agent graph flow (read-only, no code changes)