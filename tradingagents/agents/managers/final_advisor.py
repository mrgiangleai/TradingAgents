"""Final Advisor (Phase 7): synthesizes Portfolio Manager's decision with the
optional KeyVolume/Liquidity Sweep signals into one final advisory report.

Additive, not a replacement for Portfolio Manager -- see
docs/agents/final_advisor_design.md section 1 for the full rationale.
Runs unconditionally (no enable/disable flag of its own), after Portfolio
Manager, writing only "final_advisory_report" -- final_trade_decision and
everything memory_log/SignalProcessor/_log_state read are untouched.
"""

from __future__ import annotations

from tradingagents.agents.schemas import FinalAdvisoryReport, render_final_advisory_report
from tradingagents.agents.utils.agent_utils import (
    get_instrument_context_from_state,
    get_language_instruction,
)
from tradingagents.agents.utils.structured import (
    bind_structured,
    invoke_structured_or_freetext,
)

_NOT_ENABLED = "Not enabled for this run."


def _supplementary_text(state, key: str) -> str:
    """A key absent from state means the toggle was off; present means the
    node ran and rendered its own text -- which already says "no_data" and
    why, or a real signal. Either way, never invented here."""
    return state.get(key) or _NOT_ENABLED


def create_final_advisor(llm):
    structured_llm = bind_structured(llm, FinalAdvisoryReport, "Final Advisor")

    def final_advisor_node(state) -> dict:
        instrument_context = get_instrument_context_from_state(state)
        final_trade_decision = state["final_trade_decision"]
        keyvolume_text = _supplementary_text(state, "keyvolume_report")
        liquidity_sweep_text = _supplementary_text(state, "liquidity_sweep_report")

        prompt = f"""You are the Final Advisor, producing the single last advisory read for this run. This is advisory only -- no trade is ever placed automatically.

{instrument_context}

---

**Portfolio Manager's decision (already synthesizes the full analyst/debate/risk chain):**
{final_trade_decision}

**KeyVolume signal:**
{keyvolume_text}

**Liquidity Sweep signal:**
{liquidity_sweep_text}

---

Synthesize these into one final recommendation. If a signal above says "Not enabled for this run" or reports no_data/no data available, explicitly note it as unavailable in your rationale -- do not invent a value for it or guess what it might have shown, and do not let its absence lower your confidence beyond what the available signals actually justify.{get_language_instruction()}"""

        report_text = invoke_structured_or_freetext(
            structured_llm,
            llm,
            prompt,
            render_final_advisory_report,
            "Final Advisor",
        )

        # Fixed, non-model-generated line -- guaranteed present regardless of
        # whether the structured or free-text fallback path fired above
        # (Quy tac 3; see render_final_advisory_report's docstring for why
        # this can't just live inside that render function).
        report_text += "\n\n**Advisory only -- not an automated trade order.**"

        return {"final_advisory_report": report_text}

    return final_advisor_node
