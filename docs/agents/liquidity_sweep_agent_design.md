# Liquidity Sweep Agent — design — Phase 6.1/6.2a (standalone; wired in 6.3)

> Mirrors [keyvolume_agent_design.md](keyvolume_agent_design.md)'s structure exactly — only the parts that genuinely differ for Liquidity Sweep are spelled out in full; everything else (no-data short-circuit philosophy, `(symbol, date)` interface choice, "not a graph node by itself" framing) carries over unchanged and is not re-argued here.

---

## 1. Input

`tradingagents.dataflows.liquidity_sweep.load_liquidity_sweep_data(symbol, date) -> LiquiditySweepData` (Phase 6, mirrors `load_keyvolume_data`). Two shapes, same distinction as KeyVolume:

- `available=False, events=[]` — export file missing.
- `available=True, events=[...]` — export ran; `events` may be `[]` (Module 2 events are much rarer than Module 1's — see `liquidity_data_format.md` mục 4 — a 0-event day is common and legitimate, not an error).

Fields forwarded to the LLM per event: `direction`, `line_price`, `keyvolume_final_score`, `keyvolume_status`, `time`. **Not** forwarded: `sweep_strength`, `sweep_depth`, `rejection_strength` — see section 4.

## 2. Output — same shape as KeyVolume, same structured-output mechanism

```python
class LiquiditySweepSignal(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    # "no_data" excluded, same reason as KeyVolumeSignal.

class LiquiditySweepReport(BaseModel):
    signal: LiquiditySweepSignal
    confidence: Literal["low", "medium", "high"]
    evidence: str
```

Public result: `LiquiditySweepResult` dataclass (`signal: str`, `confidence: str | None`, `evidence: str`) — same shape as `KeyVolumeResult`, same `bind_structured` pattern from `agents/utils/structured.py`.

## 3. No-data behavior — identical to KeyVolume (Quy tac 4)

Missing file → `LiquiditySweepResult(signal="no_data", confidence=None, evidence="No Liquidity Sweep data available for {symbol} on {date}.")`, **no LLM call**. `available=True, events=[]` is NOT this path — goes to the LLM with an explicit "zero sweep events detected" note, expected (not enforced) response: `neutral`, low confidence.

## 4. Field selection — the one real difference from KeyVolume, and why it matters more here

KeyVolume's prompt could lean on `final_score` because Backtest-Trading-Lab's own Phase 1.5 validation found it predictive. **Liquidity Sweep has no equivalent field of its own**: Phase 2.5 batch validation (see `liquidity_data_format.md` mục 2, sourced from `architecture_handoff.md`) found `sweep_strength` shows **no detectable predictive value** (correlation ~0.001, continuation ratio 55.9% — indistinguishable from a coin flip, n=34). `sweep_depth`/`rejection_strength` were never validated either way — they are pure detection-geometry inputs to `sweep_strength`'s own (unvalidated) formula, so they carry no independent evidence either.

Consequence for the prompt (deliberately stricter than KeyVolume's field selection): `sweep_strength`, `sweep_depth`, `rejection_strength` are **excluded entirely** — not even as "context", unlike KeyVolume's lifecycle fields (`age_bars`/`test_count`/etc.), which were kept because they describe *state*, not a *score*. There is no equivalent "safe descriptive" reading for a per-event geometry number here; every one of them is a component of the exact score that failed validation.

The one field that *is* still carried on each event and *is* meaningful: `keyvolume_final_score` (copied from Module 1, validated separately in Module 1's own Phase 1.5). It describes the quality of the KeyVolume **line** that got swept, not the sweep event itself — a legitimate, different piece of evidence ("liquidity was taken around a level the market had previously respected a lot" vs. "around a weak, barely-noticed level"). The prompt says so explicitly, so the model doesn't conflate the two.

## 5. What "bullish/bearish/neutral" means for a sweep — sourced, not invented, and explicitly hedged

The export's `direction` field (`buy`/`sell`) is a fact about which side's liquidity was taken, not a score. Mapping it to a bullish/bearish read is not this document's own invention: Backtest-Trading-Lab's **own Module 3** (Market Structure Shift) already encodes exactly this mapping as its `BiasWatch.implied_direction` rule (`architecture_handoff.md`, Module 3 section): **SELL sweep -> implied BEARISH, BUY sweep -> implied BULLISH**. Reusing the same convention here is consistent with how the rest of that system already reads this field, not folklore invented for this agent.

**Explicit hedge, stated directly in the prompt**: this is an *implied* direction from a structural fact (which side got swept), not a claim that a reversal follows — Module 2's own `sweep_strength` was found to have **no** detectable predictive value at the only sample size tested so far (n=34, and Backtest-Trading-Lab's own note says this "is not a final verdict," not that sweeps are proven meaningless — just unproven). The agent must weight this appropriately: default toward `neutral`/low confidence unless the evidence (direction + swept-line quality via `keyvolume_final_score`) is unusually clear, and the evidence text must not claim a forecast the data doesn't support (mirrors KeyVolume's "structural memory strength, not a price-direction forecast" framing, section 5 there).

Multiple events in one window (rare but possible): read across all of them — if directions agree, that reinforces the read; if they conflict, that alone should push toward `neutral`. No aggregation formula is defined (Backtest-Trading-Lab's own precedent, per `project_philosophy.md` as quoted in `architecture_handoff.md`, explicitly warns against inventing new composite scores from unvalidated inputs) — the LLM reads the small list directly, same as KeyVolume's line list.

## 6. Interface — same as KeyVolume

```python
def create_liquidity_sweep_agent(llm) -> Callable[[str, str], LiquiditySweepResult]: ...
def create_liquidity_sweep_agent_node(llm): ...  # state -> {"liquidity_sweep_report": <markdown>}
```

Takes `(symbol, date)` directly for the standalone function; the node wrapper reads `company_of_interest`/`trade_date` from `AgentState`, same pattern as `keyvolume_agent.py`.

## 7. What is explicitly NOT done this session

- Not touching KeyVolume Agent's own code/config (only additive, parallel wiring — see Phase 6.3 notes in `TEST_PLAN.md`/`SESSION_LOG.md`).
- Not building Phase 7 (Market Bias / Final Advisor) — `liquidity_sweep_report` sits in state/report same as `keyvolume_report`, nothing downstream reads either yet.
- Not touching Researcher/Risk/Portfolio Manager, `analyst_execution.py`, or anything in Backtest-Trading-Lab.
