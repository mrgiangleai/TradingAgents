# Tham chiếu config — Phase 2.3 (audit, không sửa code lõi)

> Nguồn đối chiếu: `tradingagents/default_config.py` (đọc toàn bộ), `.env` hiện có trong repo (giá trị không nhạy cảm được in ra để đối chiếu), và 1 lần chạy thực tế đổi `max_debate_rounds` để kiểm chứng hành vi đổi theo config (không sửa file nguồn nào — chỉ override qua `config` dict truyền vào `TradingAgentsGraph`, đúng cách README hướng dẫn).

---

## 1. Cơ chế override: 2 lớp, không cần sửa code

1. **`_ENV_OVERRIDES`** (dòng 10–28): danh sách biến môi trường `TRADINGAGENTS_*` → key trong `DEFAULT_CONFIG`. Đọc lúc import module (`_apply_env_overrides` chạy ngay khi `DEFAULT_CONFIG` được định nghĩa). Giá trị được ép kiểu (`_coerce`) theo kiểu của default hiện có (bool/int/float/str); sai định dạng (VD: boolean không hợp lệ) → raise `ValueError` ngay, không âm thầm dùng default.
2. **Override lập trình**: bất kỳ script/CLI nào cũng có thể `config = DEFAULT_CONFIG.copy(); config["key"] = value` rồi truyền vào `TradingAgentsGraph(config=config)` — không đọc từ env, ghi đè trực tiếp dict.

`.env` trong repo hiện đã set sẵn (baseline Phase 1.2):
```
TRADINGAGENTS_LLM_PROVIDER=google
TRADINGAGENTS_DEEP_THINK_LLM=gemini-3.1-flash-lite
TRADINGAGENTS_QUICK_THINK_LLM=gemini-3.1-flash-lite
TRADINGAGENTS_OUTPUT_LANGUAGE=English
TRADINGAGENTS_MAX_DEBATE_ROUNDS=1
TRADINGAGENTS_MAX_RISK_ROUNDS=1
```

---

## 2. Bảng key → tác dụng

| Key | Default | Tác dụng | Sửa qua env? |
|---|---|---|---|
| `project_dir` | thư mục `tradingagents/` | Gốc để resolve đường dẫn nội bộ package. | Không |
| `results_dir` | `~/.tradingagents/logs` | Nơi ghi `full_states_log_{date}.json` và report tree (`save_reports`). | `TRADINGAGENTS_RESULTS_DIR` (đọc trực tiếp qua `os.getenv`, không qua `_ENV_OVERRIDES`) |
| `data_cache_dir` | `~/.tradingagents/cache` | Cache dữ liệu thị trường (yfinance CSV…) + thư mục `checkpoints/` khi bật checkpoint. | `TRADINGAGENTS_CACHE_DIR` |
| `memory_log_path` | `~/.tradingagents/memory/trading_memory.md` | File memory log (Quy tắc 1 — **luôn trỏ sang `test_memory.md` khi test**). | `TRADINGAGENTS_MEMORY_LOG_PATH` |
| `memory_log_max_entries` | `None` | Giới hạn số entry đã resolve trong memory log trước khi tự xoá bớt entry cũ nhất; entry `pending` không bao giờ bị xoá. `None` = không giới hạn. | Không có trong `_ENV_OVERRIDES` |
| `llm_provider` | `"openai"` | Chọn provider LLM (`openai`, `google`, `anthropic`, …) — quyết định `create_llm_client` dùng client nào. | `TRADINGAGENTS_LLM_PROVIDER` |
| `deep_think_llm` | `"gpt-5.5"` | Model dùng cho suy luận "sâu" — Research Manager, Portfolio Manager (2 node deep-thinking duy nhất, xem `trading_graph.py:127-138`). | `TRADINGAGENTS_DEEP_THINK_LLM` |
| `quick_think_llm` | `"gpt-5.4-mini"` | Model dùng cho mọi node còn lại (4 analyst, Bull/Bear, 3 risk debator, Trader, Reflector). | `TRADINGAGENTS_QUICK_THINK_LLM` |
| `backend_url` | `None` | Endpoint tuỳ chỉnh (vLLM/LM Studio/relay) khi dùng provider OpenAI-compatible; `None` = endpoint mặc định của provider. | `TRADINGAGENTS_LLM_BACKEND_URL` |
| `google_thinking_level` | `None` | Độ sâu suy luận riêng cho Gemini (`"high"`, `"minimal"`…). Chỉ áp dụng khi `llm_provider="google"`. | `TRADINGAGENTS_GOOGLE_THINKING_LEVEL` |
| `openai_reasoning_effort` | `None` | Tương tự cho OpenAI (`"medium"`, `"high"`, `"low"`). | `TRADINGAGENTS_OPENAI_REASONING_EFFORT` |
| `anthropic_effort` | `None` | Tương tự cho Anthropic. | `TRADINGAGENTS_ANTHROPIC_EFFORT` |
| `temperature` | `None` | Sampling temperature, forward cho mọi provider hỗ trợ; `None` = mặc định provider. Không đảm bảo output giống hệt giữa các lần chạy (model reasoning phần lớn bỏ qua temperature). | `TRADINGAGENTS_TEMPERATURE` |
| `llm_max_retries` | `None` | Số lần SDK tự retry khi gặp lỗi (VD 429); `None` = giữ default của SDK provider (thường là 2). | `TRADINGAGENTS_LLM_MAX_RETRIES` |
| `checkpoint_enabled` | `False` | Bật LangGraph checkpoint (SqliteSaver theo ticker) để resume graph nếu crash giữa chừng. Không ảnh hưởng cấu trúc node/edge — chỉ đổi cách `graph.compile()` được gọi trong `propagate()`. | `TRADINGAGENTS_CHECKPOINT_ENABLED` |
| `output_language` | `"English"` | Ngôn ngữ output report/quyết định cuối (không đổi ngôn ngữ debate nội bộ — luôn tiếng Anh để giữ chất lượng suy luận). Áp dụng qua `get_language_instruction()` được gọi trong mọi agent có output ra report. | `TRADINGAGENTS_OUTPUT_LANGUAGE` |
| `max_debate_rounds` | `1` | Số vòng debate Bull↔Bear trước khi `should_continue_debate` chuyển sang `Research Manager`. Điều kiện dừng thật: `count >= 2 * max_debate_rounds` (mỗi "vòng" = 1 lượt Bull + 1 lượt Bear). | `TRADINGAGENTS_MAX_DEBATE_ROUNDS` |
| `max_risk_discuss_rounds` | `1` | Tương tự cho debate rủi ro 3 chiều. Điều kiện dừng: `count >= 3 * max_risk_discuss_rounds` (mỗi "vòng" = Aggressive + Conservative + Neutral). | `TRADINGAGENTS_MAX_RISK_ROUNDS` |
| `max_recur_limit` | `100` | `recursion_limit` truyền cho `graph.stream/invoke` của LangGraph — trần an toàn chống vòng lặp vô hạn nếu router lỗi logic. | Không có trong `_ENV_OVERRIDES` |
| `news_article_limit` | `20` | Số bài báo tối đa lấy theo ticker (`get_news`). | Không |
| `global_news_article_limit` | `10` | Số bài báo tối đa cho tin vĩ mô toàn cầu. | Không |
| `global_news_lookback_days` | `7` | Số ngày nhìn lại cho tin vĩ mô (`get_global_news`). | Không |
| `global_news_queries` | 5 câu truy vấn cố định | Danh sách query dùng để lấy tin vĩ mô toàn cầu (Fed, S&P 500, địa chính trị, ngân hàng trung ương, hàng hoá). | Không |
| `data_vendors` | dict theo category (`core_stock_apis`, `technical_indicators`, `fundamental_data`, `news_data` → `yfinance`; `macro_data` → `fred`; `prediction_markets` → `polymarket`) | Vendor mặc định cho từng nhóm tool. Đây là **chuỗi vendor chính xác** — request không tự ý route sang vendor khác ngoài danh sách này. | Không |
| `tool_vendors` | `{}` | Override vendor cho **1 tool cụ thể**, ưu tiên cao hơn `data_vendors` cùng category. | Không |
| `benchmark_ticker` | `None` | Ép cứng 1 benchmark cho alpha calculation (ghi đè `benchmark_map`), dùng trong `Reflector`. | `TRADINGAGENTS_BENCHMARK_TICKER` |
| `benchmark_map` | 10 suffix sàn → chỉ số benchmark tương ứng, `""` (US không hậu tố) → `SPY` | Tự động chọn benchmark theo hậu tố ticker (VD `.T` → Nikkei 225) khi `benchmark_ticker` không set. | Không |

---

## 3. Kiểm chứng thực tế: đổi `max_debate_rounds` và chạy lại (memory test)

**Cách làm:** không sửa file nguồn nào. Chạy 1 script Python ngắn (xoá sau khi xong) gọi `TradingAgentsGraph(config=config)` với `config = DEFAULT_CONFIG.copy(); config["max_debate_rounds"] = 2` (baseline Phase 1.2 dùng `1`), giữ mọi key khác mặc định/từ `.env`. Đặt `TRADINGAGENTS_MEMORY_LOG_PATH` sang `test_memory.md` trước khi chạy (Quy tắc 1). Chạy ticker **MSFT** (khác AAPL của Phase 1.2 để tránh lẫn với entry pending cũ) ngày `2026-07-08`.

**Kết quả quan sát** (`final_state["investment_debate_state"]["count"]`, `final_state["risk_debate_state"]["count"]`):

| Metric | Giá trị đo được | Kỳ vọng theo config | Khớp? |
|---|---|---|---|
| `max_debate_rounds` (đã đổi) | 2 | — | — |
| `investment_debate_state.count` cuối | 4 | `2 × 2 = 4` | ✅ |
| `max_risk_discuss_rounds` (không đổi) | 1 | — | — |
| `risk_debate_state.count` cuối | 3 | `3 × 1 = 3` | ✅ |
| Thời gian chạy | 61.8 giây (so với 51.5s baseline — hợp lý vì có thêm 1 lượt Bull + 1 lượt Bear) | — | — |
| Quyết định cuối | Overweight | — | — |

→ **Hành vi đổi đúng theo config**: tăng `max_debate_rounds` từ 1 lên 2 khiến debate Bull/Bear chạy đủ 4 lượt (thay vì 2 lượt ở baseline) trước khi chuyển sang Research Manager, đúng công thức `should_continue_debate` đã ghi trong [graph_current.md](graph_current.md) mục 3.2. `max_risk_discuss_rounds` giữ nguyên `1` nên risk debate vẫn dừng ở 3 lượt như baseline — xác nhận 2 config này độc lập nhau.

**Kiểm chứng cách ly memory (Quy tắc 1):**
- ✅ `~/.tradingagents/memory/test_memory.md` có thêm entry mới: `[2026-07-08 | MSFT | Overweight | pending]` (bên cạnh entry AAPL cũ từ Phase 1.2).
- ✅ `~/.tradingagents/memory/trading_memory.md` (memory thật) — vẫn **không tồn tại**, xác nhận không bị ghi.

**Ghi chú phụ (không liên quan config, không chặn kết luận):** lần chạy này gặp cảnh báo `SSL: CERTIFICATE_VERIFY_FAILED` khi fetch StockTwits/Reddit và thiếu `FRED_API_KEY` cho macro data — cả hai đều được thiết kế graceful-degradation (agent nhận placeholder thay vì crash, đúng như comment trong `sentiment_analyst.py`), pipeline vẫn chạy xong và ra quyết định hợp lệ. Đây là vấn đề môi trường cục bộ (chứng chỉ SSL hệ thống / thiếu key optional), không phải lỗi config hay lỗi graph.

---

## 4. Ghi chú cho các phase sau

- **Phase 3 (toggle analyst)** sẽ không thêm key mới kiểu `analyst_X_enabled` vào bảng trên trong audit này — đó là việc của Bước 3.1 (thiết kế) và 3.2 (cài đặt), chưa làm ở Phase 2.
- **Quy tắc 5** (toggle chỉ sửa 1 file) áp dụng cho *graph build* (`graph/setup.py`), không áp dụng cho việc thêm config key mới trong `default_config.py` — thêm key là bình thường, không phải nơi vi phạm quy tắc.
- 2 key `results_dir` và `data_cache_dir` đọc env qua `os.getenv` trực tiếp (không qua bảng `_ENV_OVERRIDES`) — khác cơ chế với phần còn lại, cần nhớ khi audit thêm key mới ở phase sau.
