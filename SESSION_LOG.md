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

---

## Phase 2.1

Done:
- Read-only audit of `tradingagents/graph/` (setup.py, conditional_logic.py, analyst_execution.py, trading_graph.py, propagation.py, reflection.py, signal_processing.py, checkpointer.py).
- Cross-checked against the real baseline run log: `~/.tradingagents/logs/AAPL/TradingAgentsStrategy_logs/full_states_log_2026-07-08.json` (from Phase 1.2).
- Documented: node→node mermaid diagram, the 3 conditional loops (per-analyst tool loop, Bull/Bear debate, Aggressive/Conservative/Neutral risk debate), how analyst order is driven by `selected_analysts` (not hardcoded), the 8 fixed non-analyst nodes, and the true state-field reference chain (corrected an initial wrong assumption: Research Manager/Trader/Portfolio Manager do NOT read the 4 raw analyst reports directly — only Bull/Bear Researcher and the 3 risk debators do).
- No code changes made (audit only, per roadmap).

Test:
- ✅ Diagram order matches real log field order (market → sentiment → news → fundamentals → debate → plan → trader → risk debate → final decision).

Memory path used this session:
- N/A (no LLM run this session — read-only code/doc audit).

Commit:
- docs: audit agent graph

Next:
- Phase 2.2 — Agent inventory (input/output/dependency table) → `docs/architecture/agents_inventory.md`

---

## Phase 2.2

Done:
- Read-only audit of `tradingagents/agents/` (all files in analysts/, researchers/, risk_mgmt/, managers/, trader/, plus `utils/agent_utils.py` for `create_msg_delete`).
- Built full input/output table for all 12 agent nodes + the 4 `Msg Clear` / 4 `ToolNode` helper nodes, cross-checked against the Phase 1.2 baseline log (no discrepancies found).
- Recorded which downstream nodes reference each of the 4 analyst reports directly (Bull/Bear Researcher + 3 risk debators — 5 nodes, identically for all 4 analysts) and noted that Fundamentals Analyst is the only one with existing "may be unavailable" prompt language (currently gated on `asset_type != "stock"`, not on analyst-disabled) — flagged as input for Phase 3.1/3.2, not decided here.
- No code changes made (audit only, per roadmap).

Test:
- ✅ All 12 output fields in the table have non-empty values in the baseline log, in the documented order.

Memory path used this session:
- N/A (no LLM run this session — read-only code/doc audit).

Commit:
- docs: audit agents inventory

Next:
- Phase 2.3 — Config reference (`docs/architecture/config_reference.md`), including a live behavior-change test.

---

## Phase 2.3

Done:
- Read-only audit of `tradingagents/default_config.py`: documented every config key, its effect, and its env-var override path (`_ENV_OVERRIDES`), including the 2 keys (`results_dir`, `data_cache_dir`) that bypass that table via direct `os.getenv`.
- Verified behavior actually changes with config, without editing any source file: wrote a throwaway script (deleted after use) that overrides `max_debate_rounds` 1→2 via `config = DEFAULT_CONFIG.copy(); config["max_debate_rounds"] = 2`, passed to `TradingAgentsGraph(config=config)` per the README-documented pattern.
- Ran ticker MSFT / 2026-07-08 (different ticker from the Phase 1.2 AAPL baseline, to avoid mixing with its pending memory entry) with `TRADINGAGENTS_MEMORY_LOG_PATH` pointed at `test_memory.md` (Rule 1).

Test:
- ✅ `investment_debate_state.count` reached 4 (= 2 × changed `max_debate_rounds`=2), vs. baseline's 2 (= 2 × 1) — confirms the debate-loop stop condition in `conditional_logic.py` reads the config value live.
- ✅ `risk_debate_state.count` stayed at 3 (unchanged `max_risk_discuss_rounds`=1) — confirms the two round-limit configs are independent.
- ✅ `test_memory.md` got a new pending entry for MSFT; real memory path (`trading_memory.md`) still does not exist.
- Noted (non-blocking): SSL cert errors on StockTwits/Reddit fetch and missing `FRED_API_KEY` — both pre-existing graceful-degradation paths, not config or graph bugs.

Memory path used this session:
- `~/.tradingagents/memory/test_memory.md` (via `TRADINGAGENTS_MEMORY_LOG_PATH`), for the one live config-behavior-change run only.

Commit:
- docs: audit config reference

Next:
- Phase 3.1 — Design analyst toggle (not started; Phase 2 is complete as of this session).

---

## Phase 3.1

Done:
- Design-only (no code changes): wrote `docs/architecture/agent_toggle_design.md`.
- Read `tradingagents/graph/setup.py`, `analyst_execution.py`, `propagation.py`, `trading_graph.py`, and `agents/researchers/bull_researcher.py` to confirm two load-bearing facts before designing: (1) the graph-build layer (`setup_graph` + `build_analyst_execution_plan`) already supports building the graph with any subset of the 4 analysts, including raising `ValueError("at least one analyst must be selected")` on an empty set — so the "all 4 disabled" error case needs no new code; (2) `Propagator.create_initial_state()` always initializes all 4 report fields to `""` regardless of `selected_analysts`, so a disabled analyst never causes a `KeyError` downstream — only an empty string reaches the 5 nodes that read `market_report`/`sentiment_report`/`news_report`/`fundamentals_report` directly (Bull/Bear Researcher + 3 risk debators).
- Designed 4 flat boolean config keys (`enable_market_analyst`, `enable_sentiment_analyst`, `enable_news_analyst`, `enable_fundamentals_analyst`, default `True`, each independently overridable via `TRADINGAGENTS_ENABLE_*` following the existing `_ENV_OVERRIDES` pattern) instead of one nested dict, specifically because `_ENV_OVERRIDES` coercion doesn't support nested dicts and Bước 3.4's combination testing needs per-analyst env-var control.
- Decided the single file to touch in Bước 3.2/3.3 is `tradingagents/graph/trading_graph.py` — filter `selected_analysts` against the config flags right before `self.graph_setup.setup_graph(...)`, and assign the **filtered** tuple (not the raw constructor arg) to `self.selected_analysts`, because that field feeds `_run_signature()` for the checkpoint thread ID (`#1089`) — using the unfiltered tuple there would let a checkpoint silently resume under a stale analyst selection.
- Decision 3.1-A: when an analyst is disabled, its report field is left as the empty string with no added "N/A" handling in any `agents/researchers/` or `agents/risk_mgmt/` file — adding per-report empty-checks there would itself be the kind of scattered `if enabled` logic Quy tắc 5 prohibits. Documented this as an explicit, revisitable decision, not an oversight.
- Answered the roadmap's self-check question directly in the doc: disabling Sentiment Analyst leaves `sentiment_report` as `""`; Bull/Bear Researcher still read it unconditionally, producing a blank `Social media sentiment report: ` line — no crash, no special-casing added.

Test:
- N/A — design/documentation only, no code run this session (per Bước 3.1 scope).

Memory path used this session:
- N/A (no LLM run this session — design/doc work only).

Commit:
- docs: design analyst toggle

Next:
- Phase 3.2 — Implement the toggle for one analyst (pick the "easiest" one per the Bước 2.2 table — Phase 2.2 audit found no structural difference between the 4 analysts, so any one is equally easy to start with) → edit `tradingagents/default_config.py` (add the 4 flags) and `tradingagents/graph/trading_graph.py` (filtering logic, per this session's design) only.

---

## Phase 3.2

Done:
- Implemented the toggle for the first analyst — **Market Analyst** (picked per Phase 2.2's finding that all 4 are structurally equivalent, so any one works; Market Analyst is first in `ANALYST_NODE_SPECS`/the default pipeline order).
- Touched exactly 2 files, matching `docs/architecture/agent_toggle_design.md`: `tradingagents/default_config.py` (added `enable_market_analyst: True` + one `_ENV_OVERRIDES` row for `TRADINGAGENTS_ENABLE_MARKET_ANALYST`) and `tradingagents/graph/trading_graph.py` (filter `selected_analysts` against config flags right before `graph_setup.setup_graph(...)` in `TradingAgentsGraph.__init__`, assign the **filtered** tuple to `self.selected_analysts` so the checkpoint signature (`#1089`) reflects the real graph shape). No changes to `setup.py`, `analyst_execution.py`, or any `agents/` file.
- Kept the filter map (`analyst_enabled = {"market": ...}`) scoped to only the one flag that exists so far — deliberately did not pre-wire config-key lookups for the other 3 analysts, to avoid reaching into Phase 3.3's scope.

Test:
- ✅ Structural check (no LLM calls): `enable_market_analyst=False` removes exactly 3 nodes (`Market Analyst`, `tools_market`, `Msg Clear Market`) — 20 nodes → 17 nodes; `True` keeps the original 20-node graph unchanged.
- ✅ Boundary case: disabling the only requested analyst (`selected_analysts=("market",)` + `enable_market_analyst=False`) raises `ValueError: at least one analyst must be selected` at `__init__` time (fail-fast, before any LLM call) — no new code needed, reused the existing `analyst_execution.py` guard via the new filtering path.
- ✅ Full pipeline, 2 live runs (memory test): enabled (NVDA, 2026-07-09) → `market_report` has content (2993 chars), decision = Buy, 52.0s. Disabled (TSLA, 2026-07-09, `enable_market_analyst=False`) → `market_report == ""`, other 3 reports unaffected (1698/2653/3211 chars), decision = Hold, 44.2s. Neither run crashed.
- ✅ `test_memory.md` got 2 new pending entries (NVDA, TSLA); `trading_memory.md` (real memory) still does not exist.
- Full results table in `TEST_PLAN.md` under "Phase 3.2".

Memory path used this session:
- `~/.tradingagents/memory/test_memory.md` (via `TRADINGAGENTS_MEMORY_LOG_PATH`), for the 2 live pipeline runs.

Commit:
- feat: add toggle for market analyst

Next:
- Phase 3.3 — Toggle the remaining 3 analysts (Sentiment, News, Fundamentals), one commit each, same pattern as this session (extend `enable_*_analyst` in `default_config.py` + the `analyst_enabled` map in `trading_graph.py`).

---

## Phase 3.3

Done:
- Added toggles for the 3 remaining analysts — Sentiment, News, Fundamentals — repeating the exact Phase 3.2 pattern for each: 1 default key + 1 `_ENV_OVERRIDES` row in `tradingagents/default_config.py`, and 1 line added to the `analyst_enabled` dict in `tradingagents/graph/trading_graph.py`. No changes to `setup.py`, `analyst_execution.py`, or any `agents/` file — same 2-file scope as Phase 3.2, `Researcher`/`Risk`/`Portfolio Manager` untouched.
- Made 3 separate commits, one per analyst, per ROADMAP.md Bước 3.3 ("mỗi analyst 1 commit riêng"): `feat: add toggle for sentiment analyst`, `feat: add toggle for news analyst`, `feat: add toggle for fundamentals analyst`.
- All 4 config keys now exist: `enable_market_analyst`, `enable_sentiment_analyst`, `enable_news_analyst`, `enable_fundamentals_analyst` (all default `True`), each independently overridable via `TRADINGAGENTS_ENABLE_*_ANALYST`.

Test:
- ✅ Structural check (no LLM calls) for each of the 3: disabling the flag removes exactly that analyst's 3 nodes (20 → 17), leaves the other 3 analysts and all non-analyst nodes untouched.
- ✅ Live pipeline run per analyst with that analyst disabled (memory test): Sentiment off (AMD, 2026-07-09, 83.1s) → `sentiment_report == ""`, other 3 reports populated, decision produced. News off (META, 2026-07-09, 48.1s) → `news_report == ""`, same pattern. Fundamentals off (AMZN, 2026-07-09, 42.4s) → `fundamentals_report == ""`, same pattern. None crashed.
- Deliberately did not re-run live "enabled" cases per analyst (would just re-confirm the unchanged default 4-analyst baseline already covered by Phase 1.2/3.2 and by the structural check) — matches Bước 3.3's stated check criterion ("Tắt từng analyst riêng lẻ, không lỗi") without redundant LLM spend.
- Full results tables in `TEST_PLAN.md` under "Phase 3.3", including the final ✅×4 summary table required by Bước 3.3's completion criteria.

Memory path used this session:
- `~/.tradingagents/memory/test_memory.md` (via `TRADINGAGENTS_MEMORY_LOG_PATH`), for the 3 live disabled-analyst runs. `test_memory.md` now has 7 pending entries total; `trading_memory.md` (real memory) still does not exist.

Commit:
- feat: add toggle for sentiment analyst
- feat: add toggle for news analyst
- feat: add toggle for fundamentals analyst
- docs: record phase 3.3 test results (this TEST_PLAN.md / SESSION_LOG.md update)

Next:
- Phase 3.4 — Combination testing: disable 2, 3, and all 4 analysts together; verify the all-4-disabled case still fails fast with a clear error (mechanism already verified in Phase 3.2, not yet re-verified through the now-complete 4-flag config surface).