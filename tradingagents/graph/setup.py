# TradingAgents/graph/setup.py

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import (
    create_aggressive_debator,
    create_bear_researcher,
    create_bull_researcher,
    create_conservative_debator,
    create_final_advisor,
    create_fundamentals_analyst,
    create_market_analyst,
    create_msg_delete,
    create_neutral_debator,
    create_news_analyst,
    create_portfolio_manager,
    create_research_manager,
    create_sentiment_analyst,
    create_trader,
)
from tradingagents.agents.signals.keyvolume_agent import create_keyvolume_agent_node
from tradingagents.agents.signals.liquidity_sweep_agent import create_liquidity_sweep_agent_node
from tradingagents.agents.utils.agent_states import AgentState

from .analyst_execution import build_analyst_execution_plan
from .conditional_logic import ConditionalLogic

# Every target a shared conditional router can return. Each edge driven by the
# router maps all of them, so a fall-through return (e.g. under prompt/i18n/
# refactor drift in the speaker labels) can never hit a missing path_map entry
# and crash LangGraph mid-run (#1088).
DEBATE_PATH_MAP = {
    "Bull Researcher": "Bull Researcher",
    "Bear Researcher": "Bear Researcher",
    "Research Manager": "Research Manager",
}
RISK_ANALYSIS_PATH_MAP = {
    "Aggressive Analyst": "Aggressive Analyst",
    "Conservative Analyst": "Conservative Analyst",
    "Neutral Analyst": "Neutral Analyst",
    "Portfolio Manager": "Portfolio Manager",
}


class GraphSetup:
    """Handles the setup and configuration of the agent graph."""

    def __init__(
        self,
        quick_thinking_llm: Any,
        deep_thinking_llm: Any,
        tool_nodes: dict[str, ToolNode],
        conditional_logic: ConditionalLogic,
    ):
        """Initialize with required components."""
        self.quick_thinking_llm = quick_thinking_llm
        self.deep_thinking_llm = deep_thinking_llm
        self.tool_nodes = tool_nodes
        self.conditional_logic = conditional_logic

    def setup_graph(
        self,
        selected_analysts=("market", "social", "news", "fundamentals"),
        enable_keyvolume: bool = False,
        enable_liquidity_sweep: bool = False,
        quick_test_mode: bool = False,
    ):
        """Set up and compile the agent workflow graph.

        Args:
            selected_analysts (list): List of analyst types to include. Options are:
                - "market": Market analyst
                - "social": Social media analyst
                - "news": News analyst
                - "fundamentals": Fundamentals analyst
            enable_keyvolume (bool): Whether to include the KeyVolume Agent
                (Phase 5, supplementary signal, off by default).
            enable_liquidity_sweep (bool): Whether to include the Liquidity
                Sweep Agent (Phase 6, supplementary signal, off by default).
            Both flags default False, in which case the graph is shaped
            exactly as it was before Phase 5.3/6.3 -- no supplementary node,
            no extra state field ever gets written. Each enabled independently
            of the other; both can be on at once (see "supplementary_nodes"
            below).
            quick_test_mode (bool): dev/debug mode (off by default). When True,
                returns a completely separate, much smaller graph (see
                ``_setup_quick_test_graph`` below) and every line below this
                check is skipped entirely -- Full Analysis's graph-building
                code is untouched by this flag. See docs/agents/quick_test_design.md.
        """
        if quick_test_mode:
            return self._setup_quick_test_graph(enable_keyvolume, enable_liquidity_sweep)

        plan = build_analyst_execution_plan(selected_analysts)

        analyst_factories = {
            "market": lambda: create_market_analyst(self.quick_thinking_llm),
            "social": lambda: create_sentiment_analyst(self.quick_thinking_llm),
            "news": lambda: create_news_analyst(self.quick_thinking_llm),
            "fundamentals": lambda: create_fundamentals_analyst(self.quick_thinking_llm),
        }

        # Create researcher and manager nodes
        bull_researcher_node = create_bull_researcher(self.quick_thinking_llm)
        bear_researcher_node = create_bear_researcher(self.quick_thinking_llm)
        research_manager_node = create_research_manager(self.deep_thinking_llm)
        trader_node = create_trader(self.quick_thinking_llm)

        # Create risk analysis nodes
        aggressive_analyst = create_aggressive_debator(self.quick_thinking_llm)
        neutral_analyst = create_neutral_debator(self.quick_thinking_llm)
        conservative_analyst = create_conservative_debator(self.quick_thinking_llm)
        portfolio_manager_node = create_portfolio_manager(self.deep_thinking_llm)
        final_advisor_node = create_final_advisor(self.deep_thinking_llm)

        # Create workflow
        workflow = StateGraph(AgentState)

        # Add analyst nodes to the graph
        for spec in plan.specs:
            workflow.add_node(spec.agent_node, analyst_factories[spec.key]())
            workflow.add_node(spec.clear_node, create_msg_delete())
            workflow.add_node(spec.tool_node, self.tool_nodes[spec.key])

        # Add other nodes
        workflow.add_node("Bull Researcher", bull_researcher_node)
        workflow.add_node("Bear Researcher", bear_researcher_node)
        workflow.add_node("Research Manager", research_manager_node)
        workflow.add_node("Trader", trader_node)
        workflow.add_node("Aggressive Analyst", aggressive_analyst)
        workflow.add_node("Neutral Analyst", neutral_analyst)
        workflow.add_node("Conservative Analyst", conservative_analyst)
        workflow.add_node("Portfolio Manager", portfolio_manager_node)
        workflow.add_node("Final Advisor", final_advisor_node)

        # Supplementary signal agents (Phase 5.3/6.3, opt-in): each writes only
        # its own report field -- no other node reads either one yet (Phase 7
        # Final Advisor will), so enabling any subset cannot affect any
        # existing decision path. Chained in a fixed order before the first
        # analyst; each flag adds/removes exactly its own node independently.
        supplementary_nodes = []
        if enable_keyvolume:
            workflow.add_node("KeyVolume Agent", create_keyvolume_agent_node(self.quick_thinking_llm))
            supplementary_nodes.append("KeyVolume Agent")
        if enable_liquidity_sweep:
            workflow.add_node("Liquidity Sweep Agent", create_liquidity_sweep_agent_node(self.quick_thinking_llm))
            supplementary_nodes.append("Liquidity Sweep Agent")

        # Define edges
        # Start with the first analyst -- any enabled supplementary agents run
        # first, in the order above. With both off, this is a single edge
        # START -> first analyst, identical to before Phase 5.3.
        chain = [*supplementary_nodes, plan.specs[0].agent_node]
        workflow.add_edge(START, chain[0])
        for src, dst in zip(chain, chain[1:]):
            workflow.add_edge(src, dst)

        # Connect analysts in sequence
        for i, spec in enumerate(plan.specs):
            current_analyst = spec.agent_node
            current_tools = spec.tool_node
            current_clear = spec.clear_node

            # Add conditional edges for current analyst
            workflow.add_conditional_edges(
                current_analyst,
                getattr(self.conditional_logic, f"should_continue_{spec.key}"),
                [current_tools, current_clear],
            )
            workflow.add_edge(current_tools, current_analyst)

            # Connect to next analyst or to Bull Researcher if this is the last analyst
            if i < len(plan.specs) - 1:
                workflow.add_edge(current_clear, plan.specs[i + 1].agent_node)
            else:
                workflow.add_edge(current_clear, "Bull Researcher")

        # Both research-debate edges share the complete DEBATE_PATH_MAP (#1088).
        for debate_node in ("Bull Researcher", "Bear Researcher"):
            workflow.add_conditional_edges(
                debate_node,
                self.conditional_logic.should_continue_debate,
                DEBATE_PATH_MAP,
            )
        workflow.add_edge("Research Manager", "Trader")
        workflow.add_edge("Trader", "Aggressive Analyst")
        # All three risk edges share the complete RISK_ANALYSIS_PATH_MAP (#1088).
        for risk_node in ("Aggressive Analyst", "Conservative Analyst", "Neutral Analyst"):
            workflow.add_conditional_edges(
                risk_node,
                self.conditional_logic.should_continue_risk_analysis,
                RISK_ANALYSIS_PATH_MAP,
            )

        # Final Advisor (Phase 7, additive, always on -- no toggle of its own):
        # runs after Portfolio Manager, reads final_trade_decision + whichever
        # supplementary signals are present, writes only final_advisory_report.
        # Does not replace Portfolio Manager or touch final_trade_decision --
        # see docs/agents/final_advisor_design.md section 1.
        workflow.add_edge("Portfolio Manager", "Final Advisor")
        workflow.add_edge("Final Advisor", END)

        return workflow

    def _setup_quick_test_graph(self, enable_keyvolume: bool, enable_liquidity_sweep: bool):
        """Quick Test mode (dev/debug, see docs/agents/quick_test_design.md).

        Runs only KeyVolume/Liquidity Sweep (per their own existing toggles)
        and Final Advisor -- skips the entire analyst/debate/research/trader/
        risk/portfolio chain (0-12 LLM calls saved to 1-3). Reuses the exact
        same "supplementary_nodes chain" pattern as the Full Analysis path
        above, just chained to "Final Advisor" instead of the first analyst.
        Completely separate workflow object -- cannot affect setup_graph's
        Full Analysis path.
        """
        workflow = StateGraph(AgentState)
        workflow.add_node("Final Advisor", create_final_advisor(self.deep_thinking_llm, quick_test_mode=True))

        supplementary_nodes = []
        if enable_keyvolume:
            workflow.add_node("KeyVolume Agent", create_keyvolume_agent_node(self.quick_thinking_llm))
            supplementary_nodes.append("KeyVolume Agent")
        if enable_liquidity_sweep:
            workflow.add_node("Liquidity Sweep Agent", create_liquidity_sweep_agent_node(self.quick_thinking_llm))
            supplementary_nodes.append("Liquidity Sweep Agent")

        chain = [*supplementary_nodes, "Final Advisor"]
        workflow.add_edge(START, chain[0])
        for src, dst in zip(chain, chain[1:]):
            workflow.add_edge(src, dst)
        workflow.add_edge("Final Advisor", END)

        return workflow
