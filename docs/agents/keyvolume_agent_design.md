# KeyVolume Agent — design — Phase 5.1 (not wired into the graph yet)

> Scope: standalone agent only (Phase 5.1 design + 5.2a prompt + 5.2b standalone code). Pipeline integration (adding a graph node + toggle flag) is Phase 5.3 — explicitly **not** done in this session.

---

## 1. Input

`tradingagents.dataflows.keyvolume.load_keyvolume_data(symbol, date) -> KeyVolumeData` (Phase 4.3). Two shapes:

- `available=False, lines=[]` — export file missing entirely for this symbol/date.
- `available=True, lines=[...]` — export ran; `lines` may still be `[]` if the detector found zero KeyVolume lines in that window (a legitimate empty result, **not** the same as missing data — see the loader's own docstring).

Only these fields from each line are forwarded to the LLM (see "Field selection" below): `price`, `status`, `age_bars`, `test_count`, `held_count`, `broken_count`, `invalidated_reason`, `final_score`.

## 2. Output — structured, mirrors the Portfolio Manager pattern

```python
class KeyVolumeSignal(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    # "no_data" is deliberately NOT in this enum -- see section 3.

class KeyVolumeReport(BaseModel):
    signal: KeyVolumeSignal
    confidence: Literal["low", "medium", "high"]
    evidence: str   # 1-3 sentences, cites specific line(s)
```

Public result the agent function returns (`KeyVolumeResult` dataclass, not itself an LLM schema): `signal: str` (one of `bullish`/`bearish`/`neutral`/`no_data`), `confidence: str | None`, `evidence: str`. `no_data` and `confidence=None` only ever come from the short-circuit path in section 3 — the LLM itself never sees or produces the string `"no_data"`.

Uses `bind_structured`/`invoke_structured_or_freetext` from `tradingagents/agents/utils/structured.py` — the exact same helper the Portfolio Manager, Trader, and Research Manager already use, so provider fallback behavior (free-text retry when `with_structured_output` isn't supported) is inherited for free.

## 3. No-data behavior (Quy tac 4 — must not guess)

When `load_keyvolume_data(...).available` is `False`: return `KeyVolumeResult(signal="no_data", confidence=None, evidence="No KeyVolume data available for {symbol} on {date}.")` **without invoking the LLM at all**. This is a plain early return in Python, not a prompt instruction — there is no path by which the model can override or "reason past" a missing file into a guessed signal.

When `available=True` but `lines=[]` (detector ran, found nothing): this is **not** the no-data path. It goes to the LLM with an explicit note that zero lines were detected in the window; the expected (not enforced) response is `neutral` with low confidence, but the model decides, since finding zero KeyVolume lines is itself a real, if weak, observation ("no memorable volume-based level nearby"), not an error condition.

## 4. Field selection — why `final_score` only, not `creation_quality`/`anomaly_score`/`reaction_strength`

Backtest-Trading-Lab's own Phase 1.5 batch validation (see `docs/data/keyvolume_data_format.md` section 2, sourced from that project's `architecture_handoff.md`) found:
- `creation_quality`: **no predictive value** (correlation ~0.01) — audit-only.
- `survival_score` (= `final_score`, current formula): predictive (correlation ~-0.71 with a line getting broken).

`anomaly_score`/`reaction_strength`/`is_approximate` are internal audit fields with no stated validation either way. Per this project's own repeatedly-stated discipline (quoted directly in Backtest-Trading-Lab's handoff and consistent with this project's Quy tac 4 "khong doan"): don't feed an LLM unvalidated scores as if they were signal-bearing — it can rationalize a story around any number handed to it. The prompt therefore only exposes `final_score` as a numeric strength indicator; `creation_quality`/`anomaly_score`/`reaction_strength`/`is_approximate` are **not included** in the prompt at all (not even as "context") to avoid steering the model with noise dressed as signal. `price`, `status`, `age_bars`, `test_count`, `held_count`, `broken_count`, `invalidated_reason` are included because they describe the line's lifecycle (needed for the LLM to reason about "is this level still relevant"), not because they carry independent predictive weight.

## 5. What "bullish/bearish/neutral" means for a KeyVolume line (interpretive decision, flagged explicitly)

KeyVolume lines are price levels ("Market Memory" per Backtest-Trading-Lab's own system philosophy), not an inherently directional signal the way sentiment or news are. The export contract does not include the *current* market price at the KeyVolume Agent's data cutoff (only each line's own `price` at creation) as a separate field, so the agent **cannot** determine whether price is currently trading above or below a given level. Given that real constraint, honest scope for this MVP agent:

- **Bullish**: the strongest (highest `final_score`) lines are `active`/`confirmed` (still respected, not broken) — reads as "market structure / memory is currently intact," a constructive backdrop.
- **Bearish**: the strongest lines are `invalidated` with `invalidated_reason=broken` — reads as "recent structure gave way," a deteriorating backdrop.
- **Neutral**: mixed signals, uniformly low `final_score`, or zero lines detected.

This is deliberately a "structural memory strength" read, not a price-direction forecast — the prompt says so explicitly, so the LLM does not overclaim what the data can support. This is a documented, revisable interpretation (flagged per this project's own "document rather than silently decide" convention already used in Backtest-Trading-Lab's handoff for its own open questions) — Phase 7 (Market Bias / Final Advisor) is where this signal gets combined with everything else, and is the right place to revisit if this reading proves too coarse.

## 6. Interface — plain function, not a graph node (yet)

```python
def create_keyvolume_agent(llm) -> Callable[[str, str], KeyVolumeResult]:
    ...
agent = create_keyvolume_agent(llm)
result = agent("BTCUSDT", "2026-07-09")
```

Takes `(symbol, date)` directly, **not** a LangGraph `state` dict — `AgentState` has no `keyvolume_report`/similar field yet, and adding one is Phase 5.3's job (graph integration + toggle flag), not this session's. Wrapping this function into a `node(state) -> dict` shape is a thin adapter Phase 5.3 can add without touching this file's logic.

## 7. What is explicitly NOT done this session

- Not wired into `setup.py` / `AgentState` / any toggle config (Phase 5.3).
- Not touching Liquidity Sweep (Phase 6, separate signal/date format).
- Not touching Researcher/Risk/Portfolio Manager.
