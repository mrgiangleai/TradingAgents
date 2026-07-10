# Liquidity Sweep static data format — Phase 6.1 (mini-4.1)

> Nguồn: audit trực tiếp `signals/liquidity_sweep/service.py`, `export.py`, `signals/engine_kit/pipeline.py::run_core_pipeline` trong `Backtest-Trading-Lab` — không sửa file nào ở đó. Ví dụ dữ liệu là **dữ liệu thật**, sinh từ [scripts/liquidity_sweep_export.py](../../scripts/liquidity_sweep_export.py) cho BTCUSDT / 2026-07-09. Lặp lại đúng cấu trúc [keyvolume_data_format.md](keyvolume_data_format.md) (Phase 4.1) — chỉ ghi phần khác biệt so với file đó, không lặp lại toàn bộ lý luận về cách kết nối MVU/timezone đã cố định.

---

## 1. Contract đã audit (Module 2 — Liquidity Sweep Engine)

`signals/liquidity_sweep/service.py::LiquiditySweepService.run(df, lines) -> LiquiditySweepResult(events, records)` — nhưng khác Module 1, **input của Module 2 phụ thuộc output của Module 1** (`lines`, thường là `KeyVolumeService.run(df).lines`). Đây là điểm khác biệt quan trọng nhất so với KeyVolume:

- **Không được** chain 2 lệnh gọi `.run()` độc lập (`KeyVolumeService().run(df)` rồi truyền `lines` hoàn chỉnh vào `LiquiditySweepService().run(df, lines)`) — `architecture_handoff.md` ghi nhận đây là **bug lookahead thật đã từng xảy ra trong `app.py`** (nến sớm "thấy" trạng thái line ở tương lai). Cách sửa đúng: `signals/engine_kit/pipeline.py::run_core_pipeline(df)` — chạy Module 1→2(→3→4) trong **1 vòng lặp `step()` chung theo từng nến**, không lookahead.
- `scripts/liquidity_sweep_export.py` (adapter của phiên này) dùng đúng `run_core_pipeline(df)` rồi chỉ lấy `.liquidity_sweep` — **không** tự viết logic ghép Module 1+2, **không** copy bất kỳ dòng detection nào sang TradingAgents.

Module 2 (`signals/liquidity_sweep/`) là **FROZEN** — chỉ dùng qua `service.py`/`run_core_pipeline`, không sửa gì ở Backtest-Trading-Lab.

## 2. Cột dữ liệu CSV (đúng thứ tự thật, từ `export.py::event_to_dict`)

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `id` | int | ID nội bộ của event |
| `line_id` | int | ID của KeyVolume line bị "sweep" (tham chiếu chéo sang Module 1, không tự suy ra `price` — line này **không nhất thiết** trùng bất kỳ dòng nào trong `data/keyvolume/{SYMBOL}_{DATE}.csv` cùng ngày vì 2 export chạy độc lập, xem mục 4) |
| `line_price` | float | Mức giá của line bị sweep tại thời điểm này |
| `keyvolume_final_score` | float | **Copy từ Module 1** — điểm `final_score` của line bị sweep tại thời điểm sweep xảy ra. Đây LÀ field đã validate (Phase 1.5, Module 1) — phản ánh line bị sweep có phải line "mạnh" hay không |
| `keyvolume_status` | string | Status của line tại thời điểm sweep (`active`/`tested`/`confirmed`/`invalidated`) |
| `direction` | string | `buy` hoặc `sell` — hướng thanh khoản bị lấy đi (BUY sweep = quét thanh khoản phía trên; SELL sweep = quét thanh khoản phía dưới) |
| `sweep_strength` | float | **Đã validate KHÔNG có giá trị dự báo** (Phase 2.5, Backtest-Trading-Lab: correlation ~0.001, continuation ratio 55.9% — không phân biệt được với tung đồng xu, n=34 — mẫu nhỏ, "not a final verdict" theo chính ghi chú của họ) |
| `sweep_depth` | float | Độ sâu wick xuyên qua level (đơn vị ATR-normalized theo config) — mô tả hình học, không phải điểm dự báo |
| `rejection_strength` | float | Độ mạnh của nến từ chối (wick dominance) — mô tả hình học, không phải điểm dự báo |
| `index` | int | Chỉ số nến trong dataframe nguồn |
| `time` | timestamp string | Thời điểm sweep xảy ra |

**Khác biệt quan trọng nhất so với KeyVolume (Phase 4.1):** KeyVolume có `final_score` đã validate làm field chính đáng tin; Liquidity Sweep **không có field nào của riêng nó** đã validate — `sweep_strength`/`sweep_depth`/`rejection_strength` đều chỉ là mô tả hình học, chưa chứng minh dự báo được gì. Field validate duy nhất trên mỗi dòng là `keyvolume_final_score` — nhưng đó là điểm của Module 1 (line bị sweep), không phải điểm của bản thân sự kiện sweep. Đây là quyết định thiết kế agent quan trọng nhất ở Bước 6.1 (xem `docs/agents/liquidity_sweep_agent_design.md` mục 4).

Không có mảng lồng nhau nào (khác KeyVolume's `touches`) — `LiquiditySweepEvent` là immutable, không có lifecycle, nên JSON export cũng chỉ là danh sách phẳng, không có thêm thông tin gì so với CSV. MVP chỉ cần CSV.

## 3. Ví dụ dữ liệu thật (BTCUSDT, 2026-07-09)

File: [`data/liquidity/BTCUSDT_2026-07-09.csv`](../../data/liquidity/BTCUSDT_2026-07-09.csv) — 1 dòng (Module 2 hiếm hơn Module 1 đáng kể, khớp ghi chú "rất hiếm" trong `architecture_handoff.md`):

```
id,line_id,line_price,keyvolume_final_score,keyvolume_status,direction,sweep_strength,sweep_depth,rejection_strength,index,time
1,2,64110.9125,60.06777399635364,confirmed,buy,38.842159683969925,0.3182007183988402,0.3083436993347183,190,2026-06-17 22:00:00
```

Đọc: tại 2026-06-17 22:00 UTC, thị trường "sweep" thanh khoản phía BUY quanh line giá 64110.91 (line đó đang `confirmed`, `final_score=60.07` — line tương đối mạnh theo Module 1).

## 4. Quy ước file + hành vi thiếu file (đúng Quy tắc 4, giống KeyVolume)

- Đường dẫn: `data/liquidity/{SYMBOL}_{YYYY-MM-DD}.csv` — VD `data/liquidity/BTCUSDT_2026-07-09.csv`.
- `{SYMBOL}` cùng quy ước compact như KeyVolume (`BTCUSDT`, không dấu phân cách).
- Thiếu file → agent trả `No data available`, không đoán, pipeline chạy tiếp — cài đặt ở `tradingagents/dataflows/liquidity_sweep.py` (mini Bước 4.3, mirror y hệt `keyvolume.py`).
- **Lưu ý riêng cho Liquidity Sweep**: file có thể tồn tại nhưng **0 dòng** (detector chạy xong, không tìm thấy sweep event nào trong cửa sổ đó — hoàn toàn bình thường, Module 2 thưa hơn Module 1 nhiều) — đây **không phải** "thiếu dữ liệu", giống hệt phân biệt đã lập ở KeyVolume's loader (`available=True, lines=[]` khác `available=False`).

## 5. Timezone & ngày

Giống hệt KeyVolume (mục 5, `keyvolume_data_format.md`): UTC, không suffix; `{YYYY-MM-DD}` = ngày lịch UTC; `scripts/liquidity_sweep_export.py` dùng đúng cùng logic truncate chống lookahead (Quy tắc 6) — duplicate có chủ đích từ `keyvolume_export.py` để mỗi script export vẫn là 1 file CLI độc lập, chạy được một mình (xem docstring trong file đó).

## 6. Cách kết nối — không quyết định lại, dùng nguyên quyết định đã chốt ở Phase 4.1

Không có quyết định mới nào ở đây — dùng đúng cơ chế đã chọn cho KeyVolume (`keyvolume_data_format.md` mục 6): script export offline chạy bằng venv của Backtest-Trading-Lab, TradingAgents chỉ đọc file tĩnh, không API trong runtime graph. Điểm khác duy nhất: script này gọi `run_core_pipeline` (không phải `KeyVolumeService` đơn lẻ) vì Module 2 phụ thuộc dữ liệu Module 1 — lý do kỹ thuật, không phải thay đổi quyết định kiến trúc.

## 7. Việc KHÔNG làm

- Không copy logic detect sweep (wick dominance, ATR pierce...) sang TradingAgents — mọi tính toán vẫn nằm ở Backtest-Trading-Lab, chỉ đọc kết quả CSV tĩnh.
- Không đụng Module 1 (KeyVolume) hay bất kỳ file nào khác trong Backtest-Trading-Lab.
- Không thiết kế Final Advisor (Phase 7) — tài liệu này chỉ mô tả dữ liệu + cách đọc, chưa nói tới cách gộp với KeyVolume/4 analyst.
