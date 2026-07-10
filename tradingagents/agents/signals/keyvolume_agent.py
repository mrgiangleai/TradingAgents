"""KeyVolume Agent (Phase 5.1/5.2a/5.2b/5.3).

See docs/agents/keyvolume_agent_design.md for the full design rationale
(field selection, no-data short-circuit, what bullish/bearish/neutral mean
for a KeyVolume line). ``create_keyvolume_agent`` is the standalone
``(symbol, date) -> KeyVolumeResult`` function from Phase 5.1/5.2;
``create_keyvolume_agent_node`` (Phase 5.3) is a thin wrapper turning it
into a ``state -> dict`` LangGraph node, added conditionally in
``graph/setup.py`` behind the ``enable_keyvolume_agent`` config flag.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from tradingagents.agents.schemas import KeyVolumeReport
from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured
from tradingagents.dataflows.keyvolume import load_keyvolume_data

logger = logging.getLogger(__name__)


@dataclass
class KeyVolumeResult:
    """Plain result returned by the KeyVolume Agent -- not itself an LLM schema.

    ``signal="no_data"``/``confidence=None`` only ever come from the no-data
    short-circuit below; the LLM itself never produces the string "no_data"
    (see ``KeyVolumeSignal`` in schemas.py, which excludes it on purpose).
    """

    signal: str
    confidence: str | None
    evidence: str


# Only lifecycle-context fields + the one validated score (final_score) are
# exposed to the prompt -- creation_quality/anomaly_score/reaction_strength/
# is_approximate are deliberately excluded (see design doc section 4).
_RELEVANT_FIELDS = (
    "price", "status", "age_bars", "test_count",
    "held_count", "broken_count", "invalidated_reason", "final_score",
)


def _format_lines_for_prompt(lines: list[dict]) -> str:
    if not lines:
        return "(no KeyVolume lines detected in this export window)"
    formatted = []
    for line in lines:
        parts = [f"{field}={line.get(field)}" for field in _RELEVANT_FIELDS]
        formatted.append(f"- line #{line.get('id')}: " + ", ".join(parts))
    return "\n".join(formatted)


def create_keyvolume_agent(llm) -> Callable[[str, str], KeyVolumeResult]:
    """Return a callable ``(symbol, date) -> KeyVolumeResult``.

    Deliberately takes ``(symbol, date)`` directly rather than a LangGraph
    ``state`` dict -- ``AgentState`` has no KeyVolume field yet, adding one
    is Phase 5.3's job (see design doc section 6).
    """

    structured_llm = bind_structured(llm, KeyVolumeReport, "KeyVolume Agent")

    def run(symbol: str, date: str) -> KeyVolumeResult:
        data = load_keyvolume_data(symbol, date)

        if not data.available:
            # Quy tac 4: report "No data available", never guess. No LLM call.
            return KeyVolumeResult(
                signal="no_data",
                confidence=None,
                evidence=f"No KeyVolume data available for {symbol} on {date}.",
            )

        prompt = f"""You are analyzing KeyVolume line structure -- historical price levels the market has repeatedly reacted to ("Market Memory"), for {symbol} as of {date}.

Only `final_score` is a validated predictive score (higher = a level the market has kept respecting). Treat `status`/`age_bars`/`test_count`/`held_count`/`broken_count`/`invalidated_reason` only as lifecycle context for interpreting `final_score` -- they are not independent signals on their own.

Lines detected:
{_format_lines_for_prompt(data.lines)}

Read the overall structural picture: is the strongest structure currently holding (active/confirmed, high final_score) or has it recently given way (invalidated, reason=broken, high final_score)? This describes structural memory strength, not a price-direction forecast -- do not speculate about future price beyond what this line structure itself shows. If zero lines were detected, that itself is a real (if weak) observation, not an error.{get_language_instruction()}"""

        if structured_llm is not None:
            try:
                report = structured_llm.invoke(prompt)
                if report is not None:
                    return KeyVolumeResult(
                        signal=report.signal.value,
                        confidence=report.confidence,
                        evidence=report.evidence,
                    )
            except Exception as exc:
                logger.warning(
                    "KeyVolume Agent: structured-output invocation failed (%s); "
                    "falling back to a conservative neutral/low-confidence read",
                    exc,
                )

        # Free-text fallback (provider without with_structured_output, or a
        # failed structured call): prose can't be reliably parsed into
        # signal/confidence, so default conservatively instead of guessing a
        # direction this path can't actually support.
        response = llm.invoke(prompt)
        return KeyVolumeResult(
            signal="neutral",
            confidence="low",
            evidence=response.content,
        )

    return run


def render_keyvolume_result(result: KeyVolumeResult) -> str:
    """Render a KeyVolumeResult to the markdown shape used for state/report display."""
    if result.signal == "no_data":
        return f"**Signal:** no_data\n\n{result.evidence}"
    return "\n".join([
        f"**Signal:** {result.signal}",
        f"**Confidence:** {result.confidence}",
        "",
        result.evidence,
    ])


def create_keyvolume_agent_node(llm):
    """Return a LangGraph node: ``state -> {"keyvolume_report": <markdown>}``.

    Reads ``company_of_interest``/``trade_date`` already in ``AgentState``
    (same fields every analyst reads) -- no new state input required.
    Never raises: a missing export or a disabled toggle both resolve to a
    normal (if uninformative) report string, never a crashed node.
    """

    agent = create_keyvolume_agent(llm)

    def keyvolume_node(state) -> dict:
        result = agent(state["company_of_interest"], state["trade_date"])
        return {"keyvolume_report": render_keyvolume_result(result)}

    return keyvolume_node
