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
