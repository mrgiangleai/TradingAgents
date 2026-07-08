# Danh sách agent + input/output + mức phụ thuộc — Phase 2.2 (audit, không sửa code)

> Nguồn đối chiếu: `tradingagents/agents/` (đọc toàn bộ file `.py` trong `analysts/`, `researchers/`, `risk_mgmt/`, `managers/`, `trader/`, `utils/agent_utils.py`), đối chiếu log thật Bước 1.2 (`~/.tradingagents/logs/AAPL/TradingAgentsStrategy_logs/full_states_log_2026-07-08.json`) và sơ đồ [graph_current.md](graph_current.md) (Phase 2.1).

---

## 1. Bảng chính: 12 agent node (đúng thứ tự chạy, config mặc định 4 analyst)

| # | Tên agent (node label) | Input (state field đọc) | Output (state field ghi) | Dữ liệu / tool dùng | Node nào đọc output này |
|---|---|---|---|---|---|
| 1 | **Market Analyst** | `messages`, `trade_date`, `instrument_context` | `market_report`, `messages` | Tool: `get_stock_data`, `get_indicators`, `get_verified_market_snapshot` (yfinance-based, qua vòng lặp tool-call) | Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst (5 node đọc `market_report` trực tiếp) |
| 2 | **Sentiment Analyst** (wire key `social`) | `company_of_interest`, `trade_date`, `instrument_context` | `sentiment_report`, `messages` | Pre-fetch **trước khi** gọi LLM (không tool-call loop): `get_news` (Yahoo Finance), `fetch_stocktwits_messages`, `fetch_reddit_posts` | Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst |
| 3 | **News Analyst** | `messages`, `trade_date`, `asset_type`, `instrument_context` | `news_report`, `messages` | Tool: `get_news`, `get_global_news`, `get_macro_indicators` (FRED), `get_prediction_markets` | Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst |
| 4 | **Fundamentals Analyst** | `messages`, `trade_date`, `instrument_context` | `fundamentals_report`, `messages` | Tool: `get_fundamentals`, `get_balance_sheet`, `get_cashflow`, `get_income_statement` | Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst |
| 5 | **Bull Researcher** | `investment_debate_state` (history, bull_history, current_response), **4 report ở trên**, `instrument_context`, `asset_type` | `investment_debate_state` (history, bull_history, current_response, count +1) | Không tool-call — chỉ `llm.invoke(prompt)` trực tiếp với text đã có sẵn trong state | Bear Researcher (đọc `current_response` lượt sau); Research Manager (đọc `history` khi debate dừng) |
| 6 | **Bear Researcher** | Giống Bull, đối xứng (đọc `bear_history`, `current_response` là lượt Bull vừa nói) | `investment_debate_state` (history, bear_history, current_response, count +1) | Không tool-call | Bull Researcher (lượt sau); Research Manager |
| 7 | **Research Manager** | `investment_debate_state["history"]`, `instrument_context` | `investment_plan`, `investment_debate_state["judge_decision"]` | **Không đọc lại 4 report gốc** — chỉ đọc `history` đã gộp sẵn từ Bull/Bear | Trader (đọc `investment_plan`); Portfolio Manager (đọc `investment_plan`) |
| 8 | **Trader** | `company_of_interest`, `instrument_context`, `investment_plan` | `trader_investment_plan`, `messages` | **Không đọc report gốc lẫn debate history** — chỉ đọc `investment_plan` | Aggressive/Conservative/Neutral Analyst (đọc `trader_investment_plan`, biến tên cục bộ là "trader_decision"); Portfolio Manager |
| 9 | **Aggressive Analyst** | `risk_debate_state` (history, aggressive_history, current_conservative_response, current_neutral_response), **4 report gốc**, `trader_investment_plan`, `instrument_context` | `risk_debate_state` (history, aggressive_history, latest_speaker="Aggressive", current_aggressive_response, count +1) | Không tool-call | Conservative/Neutral Analyst (đọc `current_aggressive_response` lượt sau); Portfolio Manager (đọc `history` khi debate dừng) |
| 10 | **Conservative Analyst** | Đối xứng #9 (đọc `current_aggressive_response`, `current_neutral_response`) | `risk_debate_state` (…, latest_speaker="Conservative", current_conservative_response, count +1) | Không tool-call | Aggressive/Neutral Analyst (lượt sau); Portfolio Manager |
| 11 | **Neutral Analyst** | Đối xứng #9 (đọc `current_aggressive_response`, `current_conservative_response`) | `risk_debate_state` (…, latest_speaker="Neutral", current_neutral_response, count +1) | Không tool-call | Aggressive/Conservative Analyst (lượt sau); Portfolio Manager |
| 12 | **Portfolio Manager** | `risk_debate_state["history"]`, `investment_plan`, `trader_investment_plan`, `past_context` (memory log), `instrument_context` | `final_trade_decision`, `risk_debate_state["judge_decision"]` | Không đọc 4 report gốc/debate research — chỉ đọc tổng hợp risk debate + memory log | **Không có node LangGraph nào đọc tiếp** (→ `END`). Được đọc **ngoài graph** bởi `TradingAgentsGraph._log_state`, `memory_log.store_decision`, `SignalProcessor.process_signal` (`graph/signal_processing.py`) |

---

## 2. Node phụ trợ (không phải "agent" phân tích, nhưng vẫn là node trong graph)

| Node | Nguồn | Vai trò | Input | Output |
|---|---|---|---|---|
| `Msg Clear Market` / `Msg Clear Sentiment` / `Msg Clear News` / `Msg Clear Fundamentals` | `create_msg_delete()` trong `agents/utils/agent_utils.py` | Xoá toàn bộ `messages` sau khi 1 analyst xong (tránh phình context history sang analyst kế tiếp), chèn placeholder neo theo `instrument_context` + `trade_date` (không dùng chuỗi `"Continue"` trần — một số provider hiểu nhầm là nội dung câu hỏi, xem #888) | `messages`, `instrument_context`, `trade_date` | `messages` (đã xoá + placeholder mới) |
| `tools_market` / `tools_social` / `tools_news` / `tools_fundamentals` | `ToolNode(...)` trong `trading_graph.py::_create_tool_nodes` | Thực thi tool call mà analyst tương ứng yêu cầu (LangGraph `ToolNode` built-in, không phải agent tự viết) | `messages[-1].tool_calls` | `messages` (tool result) |

Các node này không xuất hiện trong `docs/agents/` tương lai (Phase 5+) vì không phải "agent" theo nghĩa roadmap dùng (agent = có LLM invoke sinh report/quyết định).

---

## 3. Quan sát phục vụ quyết định Bước 3.2 (chỉ ghi nhận dữ liệu — **không quyết định ở đây**)

Roadmap yêu cầu cột cuối "quyết định analyst nào dễ toggle nhất" — dữ liệu thu thập được:

- **Không có analyst nào trong 4 analyst được tham chiếu đích danh nhiều/ít hơn nhau về mặt cấu trúc**: cả 4 report field (`market_report`, `sentiment_report`, `news_report`, `fundamentals_report`) đều được đọc **giống hệt nhau** bởi đúng 5 node (Bull Researcher, Bear Researcher, Aggressive/Conservative/Neutral Analyst) — xem bảng mục 1. Tắt analyst nào cũng khiến 5 node đó nhận chuỗi rỗng (`""`) cho đúng 1 report tương ứng.
- **Fundamentals Analyst là analyst duy nhất đã có sẵn xử lý ngôn ngữ cho trường hợp "có thể thiếu dữ liệu"**: Bull/Bear Researcher và 3 risk debator dùng `fundamentals_label` động — `"Company fundamentals report"` khi `asset_type == "stock"`, hoặc **`"Asset fundamentals report (may be unavailable for crypto)"`** khi không phải stock (xem `bull_researcher.py:21-25`, lặp lại y hệt ở 4 file kia). Đây là dấu hiệu duy nhất trong prompt hiện tại cho thấy hệ thống đã tính đến khả năng 1 report bị thiếu/rỗng — nhưng chỉ áp dụng cho `asset_type != "stock"`, chưa áp dụng cho trường hợp "analyst bị tắt qua config" (mọi report khác dùng nhãn cứng, không có nhánh rẽ khi rỗng).
- **Market Analyst và News Analyst không có bất kỳ xử lý điều kiện nào cho trường hợp thiếu** — nhãn `"Market Research Report:"` / `"Latest World Affairs Report:"` luôn cố định trong prompt của 5 node đọc chúng.
- → Kết luận (chỉ là dữ liệu, để Bước 3.1/3.2 quyết định): nếu muốn tận dụng phần xử lý "có thể thiếu dữ liệu" đã có sẵn trong prompt, Fundamentals Analyst là candidate có ít việc phải sửa prompt nhất khi tắt. Đây **không phải quyết định cuối** — Bước 3.1 (Phase 3, chưa làm) mới là nơi chốt.

---

## 4. Đối chiếu với log thật (Bước 1.2)

Tất cả 12 field output ở bảng mục 1 đều xuất hiện có giá trị (không rỗng) trong `full_states_log_2026-07-08.json`, đúng khớp: 4 report → `investment_debate_state` (bull/bear history + judge_decision) → `investment_plan` → `trader_investment_plan` (lưu trong log dưới tên `trader_investment_decision`) → `risk_debate_state` (3 history + judge_decision) → `final_trade_decision`. Không phát hiện sai lệch giữa bảng và log thật.
