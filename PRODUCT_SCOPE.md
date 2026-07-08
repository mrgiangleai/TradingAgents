# Product Scope

## Goal

Build a custom AI Trading Assistant based on TradingAgents.

The system is advisory-only. It generates trading research reports, not automatic trade execution.

## In Scope

- Use TradingAgents as the base framework.
- Add KeyVolume analysis.
- Add Liquidity Sweep analysis.
- Add Market Bias / Final Advisor.
- Generate advisory reports.
- Use static CSV/JSON data first.

## Out of Scope

- No real-money auto trading.
- No exchange execution.
- No broker API integration.
- No live order placement.
- No upstream merge during MVP.

## Hard Rules

1. Advisory only.
2. File first, code later.
3. One session, one task.
4. Every task ends with test, session log, and commit.
5. Test/demo runs must use separate memory path.
6. Do not pull or merge upstream during MVP.