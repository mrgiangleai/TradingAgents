# Final Advisor — design — Phase 7.1 (bổ sung, không thay thế Portfolio Manager)

> Tổng hợp toàn bộ tín hiệu hiện có (chuỗi agent gốc → Portfolio Manager, + KeyVolume Agent, + Liquidity Sweep Agent) thành 1 advisory report cuối cùng. **Chỉ khuyến nghị, không auto-trade** (Quy tắc 3, `PRODUCT_SCOPE.md`).

---

## 1. Quyết định bắt buộc: Bổ sung, KHÔNG thay thế Portfolio Manager

**Final Advisor là 1 node MỚI, chạy SAU Portfolio Manager, trước END.** Không sửa, không thay thế `create_portfolio_manager`/`PortfolioDecision`/`final_trade_decision`.

Lý do:
1. **`final_trade_decision` là 1 hợp đồng đang được nhiều nơi phụ thuộc**: `memory_log.store_decision` (ghi memory log), `SignalProcessor.process_signal` (parse rating 5 bậc), `_log_state` (`full_states_log_{date}.json`), `reporting.py` (mục V). Roadmap tự ghi rõ: "Không phá format decision log hiện có (Phase 8 phụ thuộc)". Thay thế hoặc sửa Portfolio Manager sẽ đụng vào toàn bộ chuỗi này — rủi ro cao, không cần thiết.
2. **Nhất quán với pattern đã dùng ở Phase 5.3/6.3**: KeyVolume/Liquidity Sweep đã được thêm bằng cách "thêm node mới + field state mới", không sửa bất kỳ node quyết định nào có sẵn (Bull/Bear, Research Manager, Trader, Aggressive/Conservative/Neutral, Portfolio Manager). Final Advisor tiếp tục đúng nguyên tắc đó — nó là bên tiêu thụ (consumer) của `final_trade_decision`, không phải bên thay thế nó.
3. **Portfolio Manager vẫn là "quyết định của core team"** (tổng hợp risk debate + investment plan + trader plan + memory) — Final Advisor là 1 lớp tổng hợp **thêm vào sau đó**, cụ thể là lớp duy nhất trong toàn hệ thống đọc được cả 3 nguồn: quyết định của core team (`final_trade_decision`) + KeyVolume + Liquidity Sweep. Không ai khác trong graph đọc được cả 3.

→ Field mới: `final_advisory_report` (state field mới, KHÔNG ghi đè `final_trade_decision`). `_log_state`/`memory_log`/`SignalProcessor` giữ nguyên, đọc `final_trade_decision` như cũ — không đổi gì (Phase 8 sẽ là nơi quyết định có mở rộng decision log để lưu thêm `final_advisory_report` hay không, ngoài phạm vi phiên này).

## 2. Input — chỉ đọc synthesis, không đọc lại report thô

Final Advisor đọc:
- `state["final_trade_decision"]` — quyết định của Portfolio Manager (đã tổng hợp toàn bộ "agent gốc": 4 analyst → debate → research plan → trader plan → risk debate). **Luôn có mặt** (Portfolio Manager luôn chạy, không toggle được).
- `state.get("keyvolume_report")` — có thể vắng mặt hoàn toàn (tắt), hoặc có mặt với `signal=no_data` (bật nhưng thiếu file), hoặc có tín hiệu thật.
- `state.get("liquidity_sweep_report")` — 3 khả năng y hệt trên.

**Không đọc lại 4 report gốc (`market_report`/`sentiment_report`/`news_report`/`fundamentals_report`) hay lịch sử debate.** Lý do: đây là quy ước kiến trúc đã có sẵn trong toàn hệ thống — mỗi lớp tổng hợp chỉ đọc output của lớp NGAY TRƯỚC nó, không đọc ngược lại raw input (Trader chỉ đọc `investment_plan`, không đọc 4 report/debate history; Portfolio Manager chỉ đọc risk debate + 2 plan, không đọc lại 4 report gốc — xem `docs/architecture/agents_inventory.md` mục 1, dòng 7-8-12). `final_trade_decision` ĐÃ LÀ bản tổng hợp đầy đủ của toàn bộ "agent gốc" — đọc lại report thô ở đây sẽ trùng lặp ngữ cảnh Portfolio Manager đã tổng hợp kỹ, không thêm thông tin mới, chỉ làm phình prompt.

## 3. Output — structured, theo đúng pattern Portfolio Manager

```python
class FinalAdvisoryReport(BaseModel):
    recommendation: PortfolioRating   # tái dùng enum có sẵn (Buy/Overweight/Hold/Underweight/Sell)
    rationale: str                    # lý do, PHẢI nêu rõ tín hiệu nào có/thiếu/tắt
    confidence: Literal["low", "medium", "high"]
```

Tái dùng `PortfolioRating` (không tạo enum rating mới) — giữ 1 thang đánh giá duy nhất xuyên suốt hệ thống, tránh 2 thang rating khác nhau gây nhầm lẫn khi đọc report cuối.

Dùng đúng `bind_structured`/`invoke_structured_or_freetext` (`agents/utils/structured.py`) — cùng cơ chế Portfolio Manager/Trader/Research Manager/KeyVolume/Liquidity Sweep đã dùng.

**Bắt buộc theo Quy tắc 3**: `render_final_advisory_report()` luôn chèn cứng dòng disclaimer "**Advisory only — not an automated trade order.**" — không để mô hình tự quyết định có viết dòng này hay không (model có thể quên), đảm bảo dòng này LUÔN xuất hiện trong output cuối cùng.

## 4. Xử lý khi KeyVolume/Liquidity Sweep tắt hoặc thiếu dữ liệu — không tự bịa

3 khả năng cho mỗi tín hiệu bổ sung, phân biệt rõ trong prompt (không gộp làm 1):

| Trạng thái | Cách phát hiện trong node | Text đưa vào prompt |
|---|---|---|
| Tắt hẳn (toggle off) | `"keyvolume_report" not in state` | `"KeyVolume: not enabled for this run."` |
| Bật nhưng thiếu file | `state["keyvolume_report"]` bắt đầu bằng `"**Signal:** no_data"` | Nội dung thật của `keyvolume_report` (đã tự nói rõ "No KeyVolume data available for ...") |
| Bật và có dữ liệu | `state["keyvolume_report"]` có `signal` thật | Nội dung thật (markdown đã render sẵn từ Phase 5.3/6.3) |

Prompt ra lệnh tường minh: *"If a signal says 'not enabled' or 'no_data', explicitly note that in your rationale as missing/unavailable — do NOT invent a value or guess what it might have shown."* Đây chính là cơ chế "không tự bịa dữ liệu còn thiếu" — không dựa vào việc model tự giác, mà tách rõ 3 trường hợp bằng code trước khi đưa vào prompt, để model không có cách nào nhầm "not enabled" với "có dữ liệu nhưng trung tính".

Vì `final_trade_decision` luôn có mặt (Portfolio Manager không toggle được), Final Advisor **luôn** có ít nhất 1 nguồn input hợp lệ để tổng hợp — không có tình huống "input rỗng" như case "tắt cả 4 analyst" ở Phase 3. Không cần xử lý biên "báo lỗi" nào ở đây; pipeline luôn sinh ra `final_advisory_report`.

## 5. Có ảnh hưởng gì tới `final_trade_decision`/decision log không?

Không. Final Advisor không ghi vào `final_trade_decision`, `risk_debate_state`, hay bất kỳ field nào Portfolio Manager/Trader/Research Manager/memory_log/SignalProcessor/`_log_state` đang đọc/ghi. Đây là field hoàn toàn mới, độc lập. `docs: record phase 8` (tương lai, chưa làm ở đây) sẽ quyết định có đưa `final_advisory_report` vào `full_states_log_{date}.json` hay không.

## 6. Vị trí trong graph

`Portfolio Manager -> Final Advisor -> END` (thay cho `Portfolio Manager -> END` cũ). Final Advisor **không có cờ bật/tắt riêng** — đây là node cốt lõi của Phase 7 (deliverable chính của MVP, không phải tín hiệu bổ sung tuỳ chọn như KeyVolume/Liquidity Sweep), luôn chạy trong mọi cấu hình. Sửa đúng 1 chỗ trong `setup.py` (graph build).

## 7. Report cuối (`reporting.py`)

Thêm mục mới **"## VIII. Final Advisor (Advisory Only)"**, folder `8_final_advisor/`, nối tiếp sau mục VII (Liquidity Sweep) — giữ nguyên thứ tự 1-7 đã có, thuần cộng thêm, không renumber, không phá `tests/test_reporting.py`.

## 8. Việc KHÔNG làm ở Phase 7 (phiên này)

- Không thêm cờ config bật/tắt Final Advisor (luôn chạy).
- Không sửa Portfolio Manager, Trader, Research Manager, Bull/Bear, Risk debator nào.
- Không mở rộng `_log_state`/decision log (Phase 8, chưa làm).
- Không đụng KeyVolume Agent/Liquidity Sweep Agent's code hay Backtest-Trading-Lab.
