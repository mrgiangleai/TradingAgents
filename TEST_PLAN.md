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

---

## Phase 3.4 — Test tổ hợp bật/tắt nhiều analyst cùng lúc

**Ngày chạy:** 2026-07-09
**Memory path dùng:** `~/.tradingagents/memory/test_memory.md` (Quy tắc 1)
**Mục tiêu:** Kiểm chứng cơ chế toggle (Phase 3.2/3.3) ổn định khi **nhiều** analyst tắt cùng lúc, không chỉ từng cái riêng lẻ. Chỉ test — **không sửa code**, vì không phát hiện lỗi thật nào (xem kết luận cuối mục).

### Test 1 — Kiểm tra cấu trúc graph cho tổ hợp tắt 2 và tắt 3 (không tốn API)

| Tổ hợp | Cờ tắt | `selected_analysts` build ra | Số node |
|---|---|---|---|
| Tắt 2 | `enable_market_analyst=False`, `enable_sentiment_analyst=False` | `('news', 'fundamentals')` | 14 (đúng: 20 gốc − 2×3 node/analyst) |
| Tắt 3 | + `enable_news_analyst=False` | `('fundamentals',)` | 11 (chỉ còn 1 analyst + 8 node cố định + 2 node phụ trợ của nó) |

→ Số node giảm đúng tỷ lệ (mỗi analyst tắt = −3 node: agent node + tool node + msg-clear node), không có node "mồ côi" hay cạnh treo.

### Test 2 — Chạy full pipeline thật, tắt 2 và tắt 3 analyst cùng lúc (memory test)

| Tổ hợp | Ticker / ngày | `selected_analysts` | Crash? | Report tắt → rỗng đúng? | Report còn bật | Quyết định cuối | Thời gian |
|---|---|---|---|---|---|---|---|
| Tắt 2 (Market + Sentiment) | GOOGL / 2026-07-09 | `('news', 'fundamentals')` | ❌ Không | ✅ `market_report` và `sentiment_report` đều rỗng | news 3217 / fundamentals 3404 ký tự | Buy | 38.8s |
| Tắt 3 (chỉ Fundamentals bật) | NFLX / 2026-07-09 | `('fundamentals',)` | ❌ Không | ✅ `market_report`, `sentiment_report`, `news_report` đều rỗng | fundamentals 2708 ký tự | Overweight | 30.6s |

Cả 2 lần chạy: debate (Bull/Bear) và risk debate (Aggressive/Conservative/Neutral) vẫn chạy đủ vòng, Research Manager/Trader/Portfolio Manager vẫn sinh output hợp lệ dù chỉ có 1–2 report gốc — khớp dự đoán thiết kế mục 4.1/4.2 của `agent_toggle_design.md` (report rỗng không gây `KeyError`, không chặn debate).

### Test 3 — Hành vi biên: tắt cả 4 analyst cùng lúc

```
config["enable_market_analyst"] = False
config["enable_sentiment_analyst"] = False
config["enable_news_analyst"] = False
config["enable_fundamentals_analyst"] = False
TradingAgentsGraph(config=config)
```

→ Raise ngay `ValueError: at least one analyst must be selected`, trong **0.722 giây** (chỉ là overhead khởi tạo LLM client object, không có lệnh gọi API thật — `propagate()` chưa từng được gọi). Đúng như dự đoán thiết kế mục 5 của `agent_toggle_design.md`: cơ chế có sẵn từ `analyst_execution.py` (Phase 2, không phải code mới của Phase 3) đã xử lý đúng case này qua toàn bộ 4 cờ config mới, không cần sửa gì thêm.

### Kết luận: không phát hiện lỗi thật → không sửa code

Cả 3 tổ hợp (tắt 2 / tắt 3 / tắt cả 4) đều hoạt động đúng như thiết kế dự đoán ở Bước 3.1, không có crash bất ngờ, không có hành vi lệch. Theo đúng yêu cầu phiên này ("không sửa code nếu không phát hiện lỗi thật"), **không có thay đổi nào trong `tradingagents/`** ở Bước 3.4 — chỉ ghi nhận kết quả test.

### Kiểm chứng cách ly memory (Quy tắc 1)

- ✅ `test_memory.md` có thêm 2 entry mới: `[2026-07-09 | GOOGL | Buy | pending]`, `[2026-07-09 | NFLX | Overweight | pending]` (tổng 9 entry `ENTRY_END` trong file).
- ✅ `trading_memory.md` (memory thật) — vẫn không tồn tại.

### Điều kiện hoàn thành Bước 3.4

- [x] Tắt 2 analyst cùng lúc — chạy thật, không crash.
- [x] Tắt 3 analyst cùng lúc — chạy thật, không crash.
- [x] Tắt cả 4 — báo lỗi rõ ràng (`ValueError`), fail-fast, không chạy input rỗng.
- [x] Không phát hiện lỗi thật → không sửa code (đúng yêu cầu phiên này).

---

## Phase 4 (adapter) + Phase 5.1/5.2a/5.2b (standalone KeyVolume Agent)

**Ngày chạy:** 2026-07-10
**Bối cảnh:** Phiên do user yêu cầu trực tiếp (6 bước: đọc handoff → audit contract/export → chọn connection → viết adapter → test 1 symbol/date → tạo KeyVolume Agent), không tách theo từng Bước nhỏ của ROADMAP.md như thường lệ — gộp Phase 4.1/4.2/4.3 + 5.1/5.2a/5.2b vào 1 phiên vì cùng 1 mạch việc liền nhau.

### Contract đã audit (Backtest-Trading-Lab, repo sibling — không sửa gì ở đó)

`signals/keyvolume_line/service.py::KeyVolumeService` (input: OHLCV DataFrame; output: `KeyVolumeResult(lines, records)`, có sẵn `export_csv`/`export_json`) + `data/binance_data.py::get_ohlcv` (Binance qua `ccxt`). Chi tiết đầy đủ + quyết định connection (static export offline, không dùng API trong runtime) ghi ở `docs/data/keyvolume_data_format.md`.

### Test 1 — Export thật (1 symbol/date)

```
/path/to/Backtest-Trading-Lab/.venv/bin/python scripts/keyvolume_export.py BTCUSDT 2026-07-09
```

- ✅ Fetch 720 nến 1h (2026-06-10 → 2026-07-09 23:00, đúng biên UTC, không lọt nến ngày 07-10 — Quy tắc 6).
- ✅ `KeyVolumeService` sinh 9 line, ghi ra `data/keyvolume/BTCUSDT_2026-07-09.csv` — schema đúng 20 cột như audit ở `export.py::line_to_dict`.

### Test 2 — Loader (`tradingagents/dataflows/keyvolume.py::load_keyvolume_data`)

| Case | Input | Kết quả |
|---|---|---|
| File thật tồn tại | `("BTCUSDT", "2026-07-09")` | `available=True`, 9 dòng, kiểu dữ liệu ép đúng (float/int/bool), `average_bounce_strength=None` cho line chưa từng bounce (đúng, không phải lỗi parse) |
| File không tồn tại | `("ETHUSDT", "2099-01-01")` | `available=False`, `lines=[]`, không crash |

### Test 3 — KeyVolume Agent standalone (`tradingagents/agents/signals/keyvolume_agent.py`)

| Case | Input | Kết quả |
|---|---|---|
| Thiếu dữ liệu | `("ETHUSDT", "2099-01-01")` | `signal="no_data"`, `confidence=None`, **0.000s** (xác nhận không gọi LLM — short-circuit thật, không phải chỉ nhanh) |
| Dữ liệu thật, chạy 3 lần | `("BTCUSDT", "2026-07-09")` × 3 | Cả 3 lần: `signal="neutral"`, `confidence="medium"`, evidence trích dẫn cụ thể line #7 (`final_score=44.38`, `active`) đối lập với line #2/#3/#9 (`invalidated`, `broken`/`overtested`, `final_score` 33-35) — đúng thiết kế "structural memory strength", không suy đoán giá tương lai |
| Có export nhưng 0 line phát hiện | file CSV chỉ có header, `("TESTEMPTY", "2026-07-09")` | `available=True, lines=[]` (không phải no_data) → vẫn gọi LLM → `signal="neutral"`, `confidence="low"`, evidence nêu rõ "no lines detected" — đúng phân biệt "thiếu file" vs "có file, 0 kết quả" |

Prompt cuối cùng: nhúng trực tiếp trong `keyvolume_agent.py` (không tách file `docs/agents/keyvolume_agent_prompt.md` riêng — prompt đủ ngắn, đã có đầy đủ rationale ở `docs/agents/keyvolume_agent_design.md` mục 4/5, tách file thêm không tăng giá trị cho MVP).

### Điều kiện hoàn thành phiên này

- [x] Đọc handoff (`SESSION_HANDOFF.md`, `docs/architecture_handoff.md` Module 1/2) trước khi audit.
- [x] Audit contract/export thật (không đoán field).
- [x] Chọn + ghi rõ cách kết nối MVP (static export offline, không API runtime) — khớp Quy tắc "chưa dùng API ở giai đoạn MVP" đã khoá trong `ROADMAP.md`.
- [x] Viết adapter (`scripts/keyvolume_export.py` — export side; `tradingagents/dataflows/keyvolume.py` — loader side).
- [x] Test dữ liệu 1 symbol/date thật — pass.
- [x] Tạo KeyVolume Agent standalone, test cả no-data/dữ liệu thật/0-line — pass. **Chưa** wire vào graph (Phase 5.3, chưa làm).

---

## Phase 5.3 — Wire KeyVolume Agent vào graph qua toggle

**Ngày chạy:** 2026-07-10
**Memory path dùng:** `~/.tradingagents/memory/test_memory.md` (Quy tắc 1)

### File bị sửa (tối thiểu cần thiết, không đụng Trading Research Platform / Liquidity Sweep)

| File | Lý do bắt buộc phải sửa |
|---|---|
| `tradingagents/default_config.py` | Thêm cờ `enable_keyvolume_agent` (default `False` — opt-in, không đổi hành vi mặc định) + dòng `_ENV_OVERRIDES`. |
| `tradingagents/graph/setup.py` | **File build graph (Quy tắc 5)** — thêm tham số `enable_keyvolume`, chỉ `add_node`/`add_edge` "KeyVolume Agent" khi bật; khi tắt, cạnh `START -> {analyst đầu tiên}` giữ nguyên y hệt trước Phase 5.3 (không có node/cạnh mới nào được thêm). |
| `tradingagents/graph/trading_graph.py` | Đọc `config["enable_keyvolume_agent"]`, truyền vào `setup_graph(...)`; thêm `enable_keyvolume` vào `_run_signature()` (checkpoint signature) theo đúng lý do đã áp dụng cho analyst toggle ở Phase 3 (#1089). |
| `tradingagents/agents/utils/agent_states.py` | Thêm field `keyvolume_report` vào `AgentState` — bắt buộc vì LangGraph định nghĩa channel theo TypedDict schema; thiếu field này thì node mới không ghi được vào state. |
| `tradingagents/agents/signals/keyvolume_agent.py` | Thêm `render_keyvolume_result()` + `create_keyvolume_agent_node()` — bọc agent standalone (Phase 5.2, nhận `symbol, date`) thành node LangGraph (`state -> dict`), đọc `company_of_interest`/`trade_date` có sẵn trong state. |
| `tradingagents/reporting.py` | Thêm mục "VI. KeyVolume Signal" (folder `6_keyvolume/`) vào `write_report_tree` — chỉ khi `final_state.get("keyvolume_report")` có giá trị — để kết quả thực sự xuất hiện trong **report cuối** (`complete_report.md`), không chỉ nằm im trong state nội bộ. Thuần cộng thêm, không đổi số thứ tự section 1-5 có sẵn (không phá `tests/test_reporting.py`). |

**Không sửa:** `analyst_execution.py`, bất kỳ file `agents/researchers/`, `agents/risk_mgmt/`, `agents/managers/`, `agents/trader/` (Portfolio Manager/Research Manager/Trader không đọc `keyvolume_report` — đây là tín hiệu bổ sung độc lập, Phase 7 Final Advisor mới là nơi gộp lại), `propagation.py` (không cần khởi tạo `""` cho `keyvolume_report` vì hiện chưa có node nào đọc trực tiếp bằng `state["keyvolume_report"]` — chỉ `reporting.py` dùng `.get()`, đã an toàn với key vắng mặt hoàn toàn khi tắt), và không đụng bất kỳ file nào trong `Backtest-Trading-Lab/`.

### Vị trí node trong graph

`START -> KeyVolume Agent -> {analyst đầu tiên}` khi bật (chạy tuần tự, trước 4 analyst, không blocking gì khác); `START -> {analyst đầu tiên}` y hệt trước Phase 5.3 khi tắt. Không có node hiện có nào đọc `keyvolume_report` (Bull/Bear Researcher, Aggressive/Conservative/Neutral vẫn chỉ đọc 4 report gốc như cũ) — bật/tắt KeyVolume Agent không ảnh hưởng bất kỳ quyết định nào của các agent khác, kể cả khi bật.

### Test 1 — Cấu trúc graph (không tốn API)

| Case | Node "KeyVolume Agent" có mặt? | Tổng số node |
|---|---|---|
| `enable_keyvolume_agent=False` (mặc định) | ❌ Không | 20 (y hệt trước Phase 5.3) |
| `enable_keyvolume_agent=True` | ✅ Có | 21 |

### Test 2 — Full pipeline thật, 3 case bắt buộc (memory test)

| Case | Ticker/ngày | `keyvolume_report` trong `final_state` | Crash? | `final_trade_decision` | Thời gian |
|---|---|---|---|---|---|
| **ON + có dữ liệu** | BTCUSDT / 2026-07-09 (file export thật từ Phase 4/5) | `**Signal:** neutral / **Confidence:** medium` + evidence trích line #7 (`final_score=44.38`, active) vs line #2/#3/#9 (invalidated) | ❌ Không | Overweight | 67.8s |
| **ON + thiếu dữ liệu** | ETHUSDT / 2026-07-09 (không có file export) | `**Signal:** no_data` + `"No KeyVolume data available for ETHUSDT on 2026-07-09."` — không đoán | ❌ Không | Buy | 48.7s |
| **OFF** (mặc định) | SOLUSDT / 2026-07-09 | Key `keyvolume_report` **không tồn tại** trong `final_state` (`'keyvolume_report' in state` → `False`) — graph identical với trước Phase 5.3 | ❌ Không | Hold | 55.8s |

Cả 3 case: `final_trade_decision` vẫn sinh ra bình thường, không rỗng, không lỗi — xác nhận "report cuối vẫn sinh ra" đúng yêu cầu.

### Test 3 — `write_report_tree` (report cuối thực sự chứa kết quả khi bật)

Test đơn vị trực tiếp (không qua LLM, dùng state giả lập giống format `tests/test_reporting.py`):
- ✅ `keyvolume_report` có giá trị → tạo `6_keyvolume/keyvolume.md` + mục "## VI. KeyVolume Signal" xuất hiện trong `complete_report.md`.
- ✅ `keyvolume_report` vắng mặt (case OFF) → không tạo folder `6_keyvolume/`, không xuất hiện chữ "KeyVolume" nào trong `complete_report.md`.
- Không chạy được `pytest tests/test_reporting.py` trực tiếp (pytest không cài trong venv hiện tại — khai báo trong `pyproject.toml` nhưng chưa `pip install`), nhưng test thủ công ở trên dùng đúng fixture shape + đúng assertion mà `test_write_report_tree_creates_files` đã kiểm (tạo file, nội dung folder, nội dung `complete_report.md`) — không phát hiện lệch, không có regression trên 5 section cũ (1-5 vẫn giữ nguyên số thứ tự).

### Kiểm chứng cách ly memory (Quy tắc 1)

- ✅ `test_memory.md` có thêm 3 entry mới: BTCUSDT, ETHUSDT, SOLUSDT (tổng 12 entry `ENTRY_END`).
- ✅ `trading_memory.md` (memory thật) — vẫn không tồn tại.

### Điều kiện hoàn thành Bước 5.3

- [x] Cờ config bật/tắt KeyVolume Agent hoạt động đúng.
- [x] Bật + có dữ liệu → agent đọc structured data thật, kết quả vào state (`keyvolume_report`) và report cuối (`complete_report.md` mục VI).
- [x] Bật + thiếu file → không crash, không đoán (`signal="no_data"`), pipeline chạy tiếp bình thường.
- [x] Tắt → graph y hệt trước Phase 5.3, không có `keyvolume_report`, không crash.
- [x] Cả 3 case: `final_trade_decision` vẫn sinh ra.
- [x] Không sửa logic Backtest-Trading-Lab, không đụng Liquidity Sweep, không đụng Researcher/Risk/Portfolio Manager.
