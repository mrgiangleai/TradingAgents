"""Liquidity Sweep Agent (Phase 6.1/6.2a/6.2b/6.3).

Mirrors keyvolume_agent.py's structure exactly. See
docs/agents/liquidity_sweep_agent_design.md for the full design rationale
(field selection -- stricter than KeyVolume's, since sweep_strength/
sweep_depth/rejection_strength are all unvalidated -- no-data
short-circuit, what bullish/bearish/neutral mean for a sweep event).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from tradingagents.agents.schemas import LiquiditySweepReport
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured
from tradingagents.dataflows.liquidity_sweep import load_liquidity_sweep_data

logger = logging.getLogger(__name__)


@dataclass
class LiquiditySweepResult:
    """Plain result returned by the Liquidity Sweep Agent -- not itself an LLM schema.

    ``signal="no_data"``/``confidence=None`` only ever come from the no-data
    short-circuit below; the LLM itself never produces the string "no_data".
    """

    signal: str
    confidence: str | None
    evidence: str


# Only direction + swept-line quality (keyvolume_final_score, validated by
# Module 1) + lifecycle context are exposed. sweep_strength/sweep_depth/
# rejection_strength are deliberately excluded -- see design doc section 4.
_RELEVANT_FIELDS = ("direction", "line_price", "keyvolume_final_score", "keyvolume_status", "time")


def _format_events_for_prompt(events: list[dict]) -> str:
    if not events:
        return "(no Liquidity Sweep events detected in this export window)"
    formatted = []
    for event in events:
        parts = [f"{field}={event.get(field)}" for field in _RELEVANT_FIELDS]
        formatted.append(f"- event #{event.get('id')}: " + ", ".join(parts))
    return "\n".join(formatted)


def create_liquidity_sweep_agent(llm) -> Callable[[str, str], LiquiditySweepResult]:
    """Return a callable ``(symbol, date) -> LiquiditySweepResult``.

    Same interface choice as ``create_keyvolume_agent`` -- takes
    ``(symbol, date)`` directly rather than a LangGraph ``state`` dict.
    """

    structured_llm = bind_structured(llm, LiquiditySweepReport, "Liquidity Sweep Agent")

    def run(symbol: str, date: str) -> LiquiditySweepResult:
        data = load_liquidity_sweep_data(symbol, date)

        if not data.available:
            # Quy tac 4: report "No data available", never guess. No LLM call.
            return LiquiditySweepResult(
                signal="no_data",
                confidence=None,
                evidence=f"No Liquidity Sweep data available for {symbol} on {date}.",
            )

        prompt = f"""You are analyzing Liquidity Sweep events -- moments where the market took out resting liquidity around a previously-identified KeyVolume line -- for {symbol} as of {date}.

Direction convention (sourced from this system's own Market Structure Shift module, not invented here): a SELL-direction sweep implies a BEARISH read; a BUY-direction sweep implies a BULLISH read. This is an IMPLIED direction from a structural fact, not a validated forecast -- this system's own batch validation found the sweep event's own strength score has no detectable predictive value (correlation ~0.001, indistinguishable from a coin flip at the sample size tested so far). Default toward neutral/low confidence unless the evidence is unusually clear; do not claim a reversal or continuation is likely.

`keyvolume_final_score` describes the quality of the KeyVolume line that got swept (validated separately, higher = a level the market had more strongly respected before this sweep) -- weigh it, but do not use it to imply the sweep itself is validated.

Events detected:
{_format_events_for_prompt(data.events)}

If multiple events are present, read across them: agreement in direction reinforces the read; conflicting directions should push toward neutral. If zero events were detected, that itself is a real (if weak) observation, not an error.{get_language_instruction()}"""

        if structured_llm is not None:
            try:
                report = structured_llm.invoke(prompt)
                if report is not None:
                    return LiquiditySweepResult(
                        signal=report.signal.value,
                        confidence=report.confidence,
                        evidence=report.evidence,
                    )
            except Exception as exc:
                logger.warning(
                    "Liquidity Sweep Agent: structured-output invocation failed (%s); "
                    "falling back to a conservative neutral/low-confidence read",
                    exc,
                )

        # Free-text fallback: same conservative default as keyvolume_agent.py,
        # for the same reason (prose can't be reliably parsed into fields).
        response = llm.invoke(prompt)
        return LiquiditySweepResult(
            signal="neutral",
            confidence="low",
            evidence=response.content,
        )

    return run


def render_liquidity_sweep_result(result: LiquiditySweepResult) -> str:
    """Render a LiquiditySweepResult to the markdown shape used for state/report display."""
    if result.signal == "no_data":
        return f"**Signal:** no_data\n\n{result.evidence}"
    return "\n".join([
        f"**Signal:** {result.signal}",
        f"**Confidence:** {result.confidence}",
        "",
        result.evidence,
    ])


def create_liquidity_sweep_agent_node(llm):
    """Return a LangGraph node: ``state -> {"liquidity_sweep_report": <markdown>}``.

    Same pattern as ``create_keyvolume_agent_node`` -- reads
    ``company_of_interest``/``trade_date`` already in ``AgentState``.
    """

    agent = create_liquidity_sweep_agent(llm)

    def liquidity_sweep_node(state) -> dict:
        result = agent(state["company_of_interest"], state["trade_date"])
        return {"liquidity_sweep_report": render_liquidity_sweep_result(result)}

    return liquidity_sweep_node
