# Test Plan

## Setup trước mọi test (bắt buộc)

Trước khi chạy bất kỳ test/demo nào, phải set biến môi trường sau để tách khỏi memory thật:

```
export TRADINGAGENTS_MEMORY_LOG_PATH=~/.tradingagents/memory/test_memory.md
```

- Memory thật (`prod_memory.md` / mặc định `~/.tradingagents/memory/trading_memory.md`) chỉ nhận kết quả từ các lần chạy chính thức, không phải test/demo.
- Sau mỗi lần test, kiểm tra: (a) `test_memory.md` có entry mới, (b) file memory thật KHÔNG có entry mới.

---

## Phase 1.2 — Baseline demo run

**Ngày chạy:** 2026-07-09
**Memory path dùng:** `~/.tradingagents/memory/test_memory.md` (Quy tắc 1)

### Cấu hình

| Key | Value |
|---|---|
| llm_provider | google |
| deep_think_llm | gemini-3.1-flash-lite |
| quick_think_llm | gemini-3.1-flash-lite |
| max_debate_rounds | 1 |
| max_risk_discuss_rounds | 1 |
| ticker | AAPL |
| analysis_date | 2026-07-08 |
| analysts | market, social, news, fundamentals (mặc định — cả 4) |

Ghi chú: ban đầu thử provider `openai` với model `gpt-5.4-nano` (rẻ nhất) nhưng key OpenAI báo lỗi `insufficient_quota` (429 — hết hạn mức/chưa bật billing trên tài khoản). Đổi sang provider `google` với model `gemini-3.1-flash-lite` (rẻ nhất bên Google) và chạy thành công.

### Kết quả

| Metric | Value |
|---|---|
| Thời gian chạy | 51.5 giây |
| Số LLM call | 17 |
| Số tool call (đếm qua callback) | 0* |
| Tokens in | 68,968 |
| Tokens out | 7,187 |
| Quyết định cuối | Overweight (Buy, 3% position size) |

\* Callback `on_tool_start` trả về 0 dù log cho thấy nhiều tool thực sự được gọi (get_verified_market_snapshot, get_indicators, get_news, get_fundamentals, v.v.). Có thể do cách graph invoke tool node không đi qua callback này. Không chặn tiến độ — chỉ ghi chú để không hiểu nhầm là 0 tool call thật.

### Kiểm chứng cách ly memory (Quy tắc 1)

- ✅ `~/.tradingagents/memory/test_memory.md` có entry mới sau khi chạy (tag `[2026-07-08 | AAPL | Overweight | pending]`).
- ✅ `~/.tradingagents/memory/trading_memory.md` (memory thật) — file không tồn tại trước và sau khi chạy → xác nhận KHÔNG bị ghi vào.

### Điều kiện hoàn thành Bước 1.2

- [x] Có output quyết định cuối.
- [x] `test_memory.md` có entry mới.
- [x] Memory thật không có entry mới.
- [x] Baseline (thời gian, số API call, chi phí ước tính) ghi lại ở trên.

---

## Phase 3.2 — Toggle Market Analyst (analyst đầu tiên)

**Ngày chạy:** 2026-07-09
**Memory path dùng:** `~/.tradingagents/memory/test_memory.md` (Quy tắc 1)
**Analyst chọn để toggle đầu tiên:** Market Analyst — Phase 2.2 (`agents_inventory.md`) xác nhận cả 4 analyst có cấu trúc tham chiếu giống hệt nhau (không ai "dễ" hơn), nên chọn analyst đầu tiên trong `ANALYST_NODE_SPECS`/pipeline mặc định.

### Thay đổi (đúng theo thiết kế `docs/architecture/agent_toggle_design.md`)

Chỉ 2 file bị sửa:
- `tradingagents/default_config.py` — thêm key `enable_market_analyst: True` (mặc định giữ nguyên hành vi cũ) + 1 dòng trong `_ENV_OVERRIDES` cho `TRADINGAGENTS_ENABLE_MARKET_ANALYST`.
- `tradingagents/graph/trading_graph.py` — trong `TradingAgentsGraph.__init__`, lọc `selected_analysts` theo cờ config **trước** khi gọi `self.graph_setup.setup_graph(...)`, và gán tuple đã lọc (không phải tham số gốc) vào `self.selected_analysts` (dùng cho checkpoint signature, `#1089`).

Không sửa `setup.py`, `analyst_execution.py`, hay bất kỳ file `agents/` nào — đúng Quy tắc 5 và đúng phạm vi thiết kế Bước 3.1.

### Test 1 — Kiểm tra cấu trúc graph (không tốn API, không chạy LLM)

| Case | `selected_analysts` build ra | Node "Market Analyst" có mặt? | Tổng số node |
|---|---|---|---|
| `enable_market_analyst=True` (mặc định) | `('market', 'social', 'news', 'fundamentals')` | ✅ Có | 20 |
| `enable_market_analyst=False` | `('social', 'news', 'fundamentals')` | ❌ Không | 17 |

→ Đúng như thiết kế: tắt Market Analyst loại bỏ đúng 3 node liên quan (`Market Analyst`, `tools_market`, `Msg Clear Market`), không ảnh hưởng node khác.

### Test 2 — Hành vi biên: tắt analyst duy nhất được yêu cầu

`TradingAgentsGraph(selected_analysts=("market",), config={"enable_market_analyst": False, ...})` → raise ngay `ValueError: at least one analyst must be selected`, **trước khi gọi LLM nào** (fail-fast tại `__init__`). Khớp thiết kế mục 5 của `agent_toggle_design.md` — không cần code mới, cơ chế có sẵn trong `analyst_execution.py` hoạt động đúng qua đường lọc mới.

### Test 3 — Chạy full pipeline 2 lần (bật / tắt), memory test

| | Bật (mặc định) | Tắt (`enable_market_analyst=False`) |
|---|---|---|
| Ticker / ngày | NVDA / 2026-07-09 | TSLA / 2026-07-09 |
| `selected_analysts` build ra | `('market', 'social', 'news', 'fundamentals')` | `('social', 'news', 'fundamentals')` |
| Crash? | ❌ Không | ❌ Không |
| `market_report` rỗng? | Không (2993 ký tự) | ✅ Có (`""`) |
| `sentiment_report` / `news_report` / `fundamentals_report` | Có nội dung | Có nội dung (1698 / 2653 / 3211 ký tự — không bị ảnh hưởng bởi việc tắt Market Analyst) |
| Quyết định cuối sinh ra? | ✅ Buy, 2% position | ✅ Hold |
| Thời gian chạy | 52.0s | 44.2s (nhanh hơn — ít hơn 1 vòng tool-call analyst) |

Ghi chú: dùng 2 ticker khác nhau (NVDA / TSLA) để tránh trùng key `ticker+date` trong memory log giữa 2 lần chạy test, không phải vì lý do kỹ thuật khác.

Cảnh báo SSL StockTwits/Reddit + thiếu `FRED_API_KEY` xuất hiện ở cả 2 lần chạy — giống hệt cảnh báo đã ghi nhận ở Phase 1.2/2.3, là vấn đề môi trường cục bộ có sẵn từ trước, không liên quan đến thay đổi Phase 3.2, không chặn kết quả.

### Kiểm chứng cách ly memory (Quy tắc 1)

- ✅ `test_memory.md` có thêm 2 entry mới: `[2026-07-09 | NVDA | Buy | pending]` và `[2026-07-09 | TSLA | Hold | pending]` (tổng 4 entry `ENTRY_END` trong file, gồm 2 entry cũ từ Phase 1.2/2.3).
- ✅ `trading_memory.md` (memory thật) — vẫn không tồn tại.

### Điều kiện hoàn thành Bước 3.2

- [x] Cờ config `enable_market_analyst` hoạt động đúng — bật giữ nguyên hành vi cũ, tắt loại bỏ đúng node liên quan.
- [x] Chạy 2 lần (bật/tắt) với memory test, so sánh output — không crash, field đúng như thiết kế dự đoán.
- [x] Hành vi biên (tắt analyst duy nhất được chọn) báo lỗi rõ ràng, fail-fast.
- [x] Chỉ 2 file bị sửa (`default_config.py`, `graph/trading_graph.py`) — đúng tối thiểu, đúng Quy tắc 5.

---

## Phase 3.3 — Toggle 3 analyst còn lại (Sentiment, News, Fundamentals)

**Ngày chạy:** 2026-07-09
**Memory path dùng:** `~/.tradingagents/memory/test_memory.md` (Quy tắc 1)
**Pattern dùng:** Y hệt Phase 3.2 — mỗi analyst thêm 1 dòng `_ENV_OVERRIDES` + 1 default key trong `default_config.py`, và 1 dòng trong dict `analyst_enabled` của `trading_graph.py`. Không sửa `setup.py`, `analyst_execution.py`, hay bất kỳ file `agents/`. 3 commit riêng biệt, mỗi analyst 1 commit (`feat: add toggle for sentiment analyst` / `... news analyst` / `... fundamentals analyst`), theo đúng yêu cầu ROADMAP.md Bước 3.3.

### Test 1 — Kiểm tra cấu trúc graph cho từng analyst (không tốn API)

| Cờ | Bật (`True`) | Tắt (`False`) |
|---|---|---|
| `enable_sentiment_analyst` | `selected_analysts=('market','social','news','fundamentals')`, node "Sentiment Analyst" có mặt, 20 node | `selected_analysts=('market','news','fundamentals')`, node "Sentiment Analyst" biến mất, 17 node |
| `enable_news_analyst` | 20 node, node "News Analyst" có mặt | `selected_analysts=('market','social','fundamentals')`, node "News Analyst" biến mất, 17 node |
| `enable_fundamentals_analyst` | 20 node, node "Fundamentals Analyst" có mặt | `selected_analysts=('market','social','news')`, node "Fundamentals Analyst" biến mất, 17 node |

→ Mỗi cờ chỉ loại đúng 3 node của riêng analyst đó (`{Tên} Analyst`, `tools_{key}`, `Msg Clear {Tên}`), không ảnh hưởng 3 analyst còn lại — khớp thiết kế mục 4.2 của `agent_toggle_design.md`.

### Test 2 — Chạy full pipeline thật, tắt từng analyst riêng lẻ (memory test)

Theo đúng tiêu chí "Cách kiểm tra" của Bước 3.3 ("Tắt từng analyst riêng lẻ, không lỗi") — không lặp lại case "bật" bằng live run vì case đó đã được xác nhận đủ 2 lần độc lập (baseline Phase 1.2 + run "bật" Phase 3.2) và được xác nhận lại miễn phí qua Test 1 (structural, không đổi node/report so với trước Phase 3). Chỉ chạy live case "tắt" — đây là case duy nhất có rủi ro thực sự (report rỗng, ít input hơn cho debate/risk).

| Analyst tắt | Ticker / ngày | `selected_analysts` build ra | Crash? | Report tương ứng rỗng? | 3 report còn lại | Quyết định cuối | Thời gian |
|---|---|---|---|---|---|---|---|
| Sentiment | AMD / 2026-07-09 | `('market', 'news', 'fundamentals')` | ❌ Không | ✅ `sentiment_report` rỗng | market 2098 / news 2703 / fundamentals 3026 ký tự | Overweight | 83.1s |
| News | META / 2026-07-09 | `('market', 'social', 'fundamentals')` | ❌ Không | ✅ `news_report` rỗng | market 2430 / sentiment 1895 / fundamentals 3137 ký tự | Overweight | 48.1s |
| Fundamentals | AMZN / 2026-07-09 | `('market', 'social', 'news')` | ❌ Không | ✅ `fundamentals_report` rỗng | market 2680 / sentiment 1647 / news 3028 ký tự | Overweight | 42.4s |

Cảnh báo SSL StockTwits/Reddit + thiếu `FRED_API_KEY` xuất hiện ở các lần chạy có Sentiment/News analyst hoạt động — giống hệt cảnh báo đã ghi nhận từ Phase 1.2, không liên quan thay đổi Phase 3.3, không chặn kết quả.

### Kiểm chứng cách ly memory (Quy tắc 1)

- ✅ `test_memory.md` có thêm 3 entry mới: `[2026-07-09 | AMD | Overweight | pending]`, `[2026-07-09 | META | Overweight | pending]`, `[2026-07-09 | AMZN | Overweight | pending]` (tổng 7 entry `ENTRY_END` trong file).
- ✅ `trading_memory.md` (memory thật) — vẫn không tồn tại.

### Bảng tổng hợp — đủ 4 analyst có toggle hoạt động (yêu cầu hoàn thành Bước 3.3)

| Analyst | Config key | Env var | Toggle hoạt động đúng? |
|---|---|---|---|
| Market | `enable_market_analyst` | `TRADINGAGENTS_ENABLE_MARKET_ANALYST` | ✅ (Phase 3.2) |
| Sentiment | `enable_sentiment_analyst` | `TRADINGAGENTS_ENABLE_SENTIMENT_ANALYST` | ✅ (Phase 3.3) |
| News | `enable_news_analyst` | `TRADINGAGENTS_ENABLE_NEWS_ANALYST` | ✅ (Phase 3.3) |
| Fundamentals | `enable_fundamentals_analyst` | `TRADINGAGENTS_ENABLE_FUNDAMENTALS_ANALYST` | ✅ (Phase 3.3) |

### Điều kiện hoàn thành Bước 3.3

- [x] Cả 3 analyst còn lại tắt riêng lẻ được, không lỗi.
- [x] Pattern giống hệt Phase 3.2 (chỉ 2 file `default_config.py` + `trading_graph.py`, không đụng `setup.py`/`analyst_execution.py`/`agents/`).
- [x] 3 commit riêng biệt, mỗi analyst 1 commit.
- [x] Bảng trên đánh ✅ đủ 4 analyst.
