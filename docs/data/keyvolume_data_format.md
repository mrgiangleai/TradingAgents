# KeyVolume static data format + connection method — Phase 4.1

> Nguồn: audit trực tiếp `signals/keyvolume_line/service.py`, `export.py`, `data/binance_data.py`, `SESSION_HANDOFF.md`, `docs/architecture_handoff.md` (Module 1) trong `Backtest-Trading-Lab` (repo sibling, gọi là "Trading Research Platform" trong yêu cầu phiên này) — không sửa file nào trong repo đó. Ví dụ dữ liệu bên dưới là **dữ liệu thật**, sinh ra từ [scripts/keyvolume_export.py](../../scripts/keyvolume_export.py) cho BTCUSDT / 2026-07-09.

---

## 1. Contract đã audit ở Backtest-Trading-Lab (Module 1 — KeyVolume Engine)

`signals/keyvolume_line/service.py::KeyVolumeService` là public API layer chính thức (docstring của file này tự nhận là điểm vào cho "future AI/backtest orchestration" — đúng vai trò TradingAgents đang đóng):

- Input: `KeyVolumeService(config).run(df)` với `df` là OHLCV DataFrame (`timestamp, open, high, low, close, volume`).
- Output: `KeyVolumeResult(lines: List[KeyVolumeLine], records: List[dict])`.
- Export có sẵn: `service.export_csv(result, path)` / `service.export_json(result, path)` / `service.to_csv_string(result)` / `service.to_json_string(result)` — tận dụng nguyên vẹn, không viết lại logic export.
- Module 1 (`signals/keyvolume_line/`) là **FROZEN** ở Backtest-Trading-Lab (detector/scoring không được sửa) — chỉ dùng qua `service.py`, không import `detector.py` trực tiếp.

Nguồn OHLCV: `data/binance_data.py::get_ohlcv` (Binance qua `ccxt`, dùng symbol dạng `BTC/USDT`) — crypto giao dịch 24/7, không theo giờ sàn Mỹ như equity.

## 2. Cột dữ liệu CSV (đúng thứ tự thật, từ `export.py::line_to_dict`)

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | int | ID nội bộ của line (thứ tự phát hiện, không phải giá trị tuyệt đối ổn định giữa các lần chạy) |
| `price` | float | Mức giá của KeyVolume line |
| `created_at` | timestamp string | Thời điểm line được tạo |
| `source_segment_start` / `source_segment_end` | int | Chỉ số nến bắt đầu/kết thúc đoạn tạo ra line |
| `status` | string | `active` / `tested` / `confirmed` / `invalidated` (lifecycle) |
| `test_count` | int | Số lần line bị test lại |
| `age_bars` | int | Số nến kể từ khi tạo |
| `invalidated_reason` | string hoặc rỗng | `broken` / `overtested` / `expired`, rỗng nếu line vẫn `active` |
| `is_approximate` | bool | Cờ audit nội bộ |
| `anomaly_score`, `reaction_strength` | float | Điểm audit, không phải tín hiệu giao dịch |
| `creation_quality` | float | **Đã validate KHÔNG có giá trị dự báo** (Phase 1.5, Backtest-Trading-Lab) — chỉ audit, không dùng làm tín hiệu |
| `survival_bars`, `held_count`, `broken_count` | int | Thống kê lifecycle |
| `average_bounce_strength`, `max_bounce_strength` | float hoặc rỗng | Rỗng khi `held_count == 0` (chưa từng bị test giữ) — **không phải dữ liệu thiếu do lỗi**, là giá trị hợp lệ "chưa có bounce nào" |
| `survival_score` | float | **Đã validate CÓ giá trị dự báo** (correlation ~-0.71 với việc line có bị "broken" hay không — Phase 1.5) |
| `final_score` | float | = `survival_score` nguyên văn (Backtest-Trading-Lab's `compute_final_score` hiện tại không cộng thêm gì) — đây là field duy nhất được khuyến nghị dùng làm tín hiệu chính |

**Field quan trọng nhất cho KeyVolume Agent (Phase 5): `final_score`** — field khác chỉ để audit/context, không có giá trị dự báo đã được Backtest-Trading-Lab tự validate (xem `docs/architecture_handoff.md` Module 1 ở đó).

Export JSON (`service.export_json`) có thêm mảng `touches` (audit trail từng lần test) — **không dùng trong MVP**, chỉ CSV summary là đủ cho KeyVolume Agent; ghi nhận để không quên nếu Phase 9 cần audit sâu hơn.

## 3. Ví dụ dữ liệu thật (BTCUSDT, 2026-07-09)

File: [`data/keyvolume/BTCUSDT_2026-07-09.csv`](../../data/keyvolume/BTCUSDT_2026-07-09.csv) — sinh thật bằng `scripts/keyvolume_export.py`, 9 dòng. 2 dòng đầu:

```
id,price,created_at,source_segment_start,source_segment_end,status,test_count,age_bars,invalidated_reason,is_approximate,anomaly_score,reaction_strength,creation_quality,survival_bars,held_count,broken_count,average_bounce_strength,max_bounce_strength,survival_score,final_score
1,62375.246458333335,2026-06-11 17:00:00,41,41,invalidated,1,162,broken,True,2.510040457973372,1.8307061497132628,55.081119958231355,162,0,1,,,9.719999999999999,9.719999999999999
7,58556.25,2026-07-01 13:00:00,517,517,active,0,198,,True,2.7618072887132668,2.265557522123891,62.79875788698095,198,0,0,,,44.379999999999995,44.379999999999995
```

Line `id=7` là dòng duy nhất còn `active` (chưa bị `broken`/`overtested`), `final_score=44.38` — cao nhất trong 9 line, khớp trực giác (line còn sống thường có `survival_score` cao hơn line đã "chết").

## 4. Quy ước file (đúng Quy tắc 4, ROADMAP.md — không đổi)

- Đường dẫn: `data/keyvolume/{SYMBOL}_{YYYY-MM-DD}.csv` — VD `data/keyvolume/BTCUSDT_2026-07-09.csv`.
- `{SYMBOL}` là dạng compact không dấu phân cách (`BTCUSDT`, khớp cách CLI/ticker của TradingAgents đã dùng cho crypto — xem `tradingagents/dataflows/symbol_utils.py`), **khác** với dạng `BTC/USDT` mà Backtest-Trading-Lab/ccxt dùng nội bộ. `scripts/keyvolume_export.py::to_ccxt_symbol`/`to_file_symbol` là nơi duy nhất chuyển đổi 2 chiều này.
- Thiếu file → agent trả `No data available`, không đoán, pipeline chạy tiếp (Quy tắc 4) — cài đặt cụ thể ở `tradingagents/dataflows/keyvolume.py` (Phase 4.3).

## 5. Timezone & ngày (bắt buộc theo Bước 4.1)

- Toàn bộ timestamp trong CSV là **UTC, không có suffix timezone** (giữ nguyên định dạng thật từ `pandas.to_datetime(unit="ms")` trong `data/binance_data.py` — không có thông tin timezone gắn kèm, nhưng nguồn là Binance nên **ngầm định là UTC**).
- `{YYYY-MM-DD}` trong tên file = **ngày lịch UTC**, không phải ngày theo giờ sàn Mỹ (khác với cách TradingAgents dùng `trade_date` cho equity qua yfinance, vốn thường ngầm định giờ New York). Đây là điểm khác biệt cố ý — crypto giao dịch 24/7, không có "giờ đóng cửa sàn" để neo theo.
- `scripts/keyvolume_export.py` định nghĩa "dữ liệu của ngày D" = mọi nến có `timestamp < (D + 1 ngày) 00:00 UTC` — tức trọn 24 giờ UTC của ngày D, **không có nến nào từ ngày D+1 trở đi lọt vào** (Quy tắc 6 — chống lookahead). Đây là bước truncate chủ động sau khi fetch (không tin tưởng riêng `since_ms`/`limit` của ccxt tự giới hạn đúng biên trên).

## 6. Cách kết nối MVP — quyết định (Bước 3 của phiên này)

**Đã chọn: script export offline, chạy 1 lần bằng tay/CI, không có API call nào trong runtime graph của TradingAgents.**

Lý do và các phương án đã cân nhắc:

| Phương án | Quyết định | Lý do |
|---|---|---|
| **A. Static CSV/JSON export, sinh offline** (đã chọn) | ✅ | Đúng quyết định đã khoá sẵn trong `ROADMAP.md` ("Chưa dùng API ở giai đoạn MVP"). Không có lệnh gọi mạng nào trong `propagate()`; runtime chỉ đọc file tĩnh — khớp Quy tắc 4 và triết lý "advisory, không phụ thuộc uptime của hệ thống khác" của dự án. |
| B. TradingAgents import trực tiếp package `signals.keyvolume_line` của Backtest-Trading-Lab (coupling code) | ❌ Từ chối | Backtest-Trading-Lab thay đổi gần như mỗi phiên (Module 3-10 đang phát triển tích cực, xem `SESSION_HANDOFF.md`) — coupling trực tiếp sẽ làm TradingAgents vỡ theo mỗi lần refactor bên kia. Cũng yêu cầu `ccxt` trong venv của TradingAgents (không cần thiết cho advisory report). |
| C. Live API call tới Backtest-Trading-Lab (REST endpoint mới) | ❌ Từ chối | Backtest-Trading-Lab không có API server — sẽ phải xây mới, vi phạm trực tiếp "Chưa dùng API ở giai đoạn MVP" đã khoá. |

**Cơ chế cụ thể (phương án A):**
1. `scripts/keyvolume_export.py` (sống trong repo TradingAgents, nhưng **phải chạy bằng Python venv của Backtest-Trading-Lab** vì cần `ccxt` + import `signals.keyvolume_line`/`data.binance_data` của repo đó). Đây là **adapter/điểm nối duy nhất** giữa 2 repo — không sửa gì bên Backtest-Trading-Lab (Module 1 vẫn FROZEN, chỉ dùng qua `service.py` đã public).
2. Script fetch OHLCV qua `get_ohlcv`, chạy `KeyVolumeService.run(df)`, ghi CSV vào `data/keyvolume/{SYMBOL}_{YYYY-MM-DD}.csv` trong TradingAgents.
3. `tradingagents/dataflows/keyvolume.py::load_keyvolume_data(symbol, date)` (Phase 4.3) chỉ đọc file tĩnh này — không import, không gọi mạng, không phụ thuộc Backtest-Trading-Lab có đang chạy hay không.

Chạy lại ví dụ (Bước 5 của phiên này):
```
/path/to/Backtest-Trading-Lab/.venv/bin/python scripts/keyvolume_export.py BTCUSDT 2026-07-09
```

## 7. Việc KHÔNG làm ở Phase 4.1 (nhắc phạm vi)

- Không tạo `data/liquidity/` hay đặc tả format Liquidity Sweep — phiên này chỉ scope KeyVolume (Phase 6 làm sau, lặp cấu trúc y hệt).
- Không sửa bất kỳ file nào trong `Backtest-Trading-Lab/` (chỉ đọc + chạy script export bằng venv của repo đó).
- Không đưa `final_score` hay bất kỳ field nào vào logic quyết định của agent ở tài liệu này — đó là việc của Phase 5 (`docs/agents/keyvolume_agent_design.md`).
