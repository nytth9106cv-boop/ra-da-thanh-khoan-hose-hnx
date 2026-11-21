# Từ điển dữ liệu

Cơ sở dữ liệu: `data/liquidity.db` (SQLite). Nguồn: SSI API (dữ liệu cuối ngày).
Ngày lưu dạng `YYYY-MM-DD`. Ô rỗng từ SSI được lưu là `NULL`.
Giá trị giao dịch `value` được lưu bằng đồng. Trường giá OHLC có thể do nguồn SSI
trả theo đơn vị nghìn đồng, nên phần tính toán trần/sàn sẽ quy đổi giá về đồng
trước khi so sánh.

## 1. Bảng `daily_ohlc` (endpoint `/api/v3/data/ohlc`)

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| symbol | TEXT | Mã chứng khoán (khóa chính cùng trading_date) |
| trading_date | TEXT | Ngày giao dịch |
| open, high, low, close | REAL | Giá mở, cao, thấp, đóng cửa |
| volume | REAL | Khối lượng khớp |
| value | REAL | Giá trị khớp lệnh (đồng) |

Lưu ý: SSI không trả dòng cho ngày mã không giao dịch; khi tính, ngày thiếu được
coi là khối lượng và giá trị bằng 0, giá đóng cửa giữ giá gần nhất.

## 2. Bảng `foreign_flow` (endpoint `/api/v3/data/securitiesSummary`)

| Cột | Kiểu | Ý nghĩa | Trường SSI |
|---|---|---|---|
| symbol, trading_date | TEXT | Khóa chính | symbol, tradingDate |
| buy_vol, sell_vol | REAL | Khối lượng nước ngoài mua, bán | totalForeignBuy, totalForeignSell |
| buy_val, sell_val | REAL | Giá trị nước ngoài mua, bán (đồng) | totalForeignBuyValue, totalForeignSellValue |
| remain_room | REAL | Room nước ngoài còn lại (cổ phiếu) | remainForeignRoom |
| total_room | REAL | Tổng room nước ngoài | totalForeignRoom |

Dữ liệu room có thể rỗng hoặc không hợp lệ (âm, còn lại vượt tổng, tổng bằng 0).
Mã nguồn điền lại room rỗng bằng giá trị hợp lệ gần nhất (tối đa 10 ngày) và gắn
cờ `room_anomaly` cho số bất thường thật.

## 3. Bảng `price_limits` (endpoint `/api/v3/data/masterdata`)

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| symbol, trading_date | TEXT | Khóa chính |
| board | TEXT | Sàn (HOSE, HNX, UPCOM); SSI dùng `board`, không phải `exchange` |
| ceiling, floor | REAL | Giá trần, giá sàn |
| ref_price | REAL | Giá tham chiếu |

## 4. Bảng `corporate_actions` (sự kiện quyền)

| Cột | Ý nghĩa |
|---|---|
| symbol | Mã chứng khoán |
| exright_date | Ngày giao dịch không hưởng quyền |
| record_date | Ngày chốt danh sách |
| issue_date | Ngày thực hiện |
| event_title | Nội dung sự kiện |
| exchange | Sàn niêm yết do SSI trả về |
| ratio | Tỷ lệ, ghi nguyên văn từ SSI |

Bảng do `src/data/ingest_actions.py` tạo, gồm cả sự kiện của sàn khác (ví dụ UPCoM);
ứng dụng chỉ dùng theo mã đang xem.
Khóa chính logic của bảng là `(symbol, event_title, exright_date, record_date)`.
Chỉ các sự kiện được nạp thành công mới xuất hiện trong bảng.

## 5. Danh sách mã `config/universes/*.txt`

Mỗi dòng một mã; dòng bắt đầu bằng `#` là chú thích nguồn. Lấy từ SSI
`securitiesByBoard` (HOSE và HNX theo board; VN30, VN100 theo index; HOSE bổ sung
từ VN100 vì endpoint board không trả HPG). Chỉ giữ loại `Stock`.
HAX (HOSE) cũng bị endpoint board bỏ sót nên được bổ sung qua `EXTRA_SYMBOLS`
trong `src/data/universe.py`.

## 6. Bảng điểm (kết quả của `build_snapshot`, một dòng mỗi mã)

| Cột | Ý nghĩa |
|---|---|
| symbol, exchange | Mã và sàn (HOSE, HNX) |
| date, close | Ngày dữ liệu thật gần nhất và giá đóng cửa ngày đó |
| n_sessions | Số phiên trong lịch chung tính từ ngày mã có dữ liệu đầu tiên |
| traded_days | Số ngày có giao dịch trong cửa sổ tính |
| adv | Giá trị giao dịch bình quân trong cửa sổ (đồng) |
| amihud | Độ trượt giá Amihud: trung bình \|lợi suất ngày\| / giá trị giao dịch (tỷ đồng) |
| days_to_liq | Số phiên để bán hết = khoản / (tỷ lệ tham gia × adv) |
| vol_z | Z-score khối lượng so với 60 phiên trước |
| s_amihud, s_dtl | Thứ hạng phân vị (0 đến 1) trong sàn của hai thành phần |
| risk_score | Điểm khó mua bán 0 đến 100 (càng cao càng khó) |
| level | Cao, Trung bình, Thấp (tam phân vị của điểm trong sàn). Mã có điểm nhưng giao dịch thưa (`thin`) luôn là Cao. Mã không có điểm (không giao dịch trong cửa sổ hoặc mới niêm yết) là Thiếu dữ liệu |
| net_5d_ratio | Nước ngoài mua trừ bán ròng 5 phiên / (5 × ADV20); âm là bán ròng |
| sell_streak | Số phiên nước ngoài bán ròng liên tiếp |
| room_used_pct | Phần room nước ngoài đã dùng |
| stale | Mã không có dữ liệu phiên mới nhất của thị trường |
| thin | Số ngày giao dịch trong cửa sổ dưới ngưỡng `min(10, window)` |
| at_ceiling, at_floor | Giá đóng cửa chạm trần, sàn cùng ngày |
| room_anomaly, room_full, room_missing | Room bất thường, đã hết, thiếu dữ liệu |
| vol_low, vol_high | Khối lượng thuộc nhóm thấp, cao bất thường (phân vị trong sàn) |
| foreign_out | Nước ngoài bán ròng thuộc nhóm mạnh nhất trong sàn |
| dtl_alert | Số phiên để bán hết vượt mốc người dùng đặt |
| alerts | Chuỗi chữ mô tả các cảnh báo |

## 7. Quy tắc tính toán bổ sung

- `n_sessions` là số dòng trong lịch phiên chung của thị trường tính từ ngày mã
  đó có dữ liệu OHLC đầu tiên. SSI không trả dòng cho ngày không giao dịch; khi
  ghép lịch, các ngày thiếu được gán `volume = 0`, `value = 0`, còn `close` giữ
  giá đóng cửa gần nhất.
- `traded_days` đếm số ngày có `value > 0` trong cửa sổ đang tính.
- `thin` đúng với điều kiện `traded_days < min(10, window)`. Cấu hình cửa sổ
  của giao diện mặc định là 20 phiên.
- `adv` là trung bình `value` trong cửa sổ, tối thiểu đủ số phiên của cửa sổ.
- `amihud` là trung bình trượt giá tuyệt đối trên giá trị giao dịch (tỷ đồng),
  theo cửa sổ đang tính và tối thiểu 10 quan sát hoặc bằng cửa sổ nếu cửa sổ nhỏ
  hơn 10.
- `days_to_liq = position_value / (participation × adv)`, trong đó hai tham số
  có thể điều chỉnh trong giao diện; mặc định là 50 tỷ đồng và tham gia 20%.
- `vol_z` dùng trung bình và độ lệch chuẩn 60 phiên trước, không gồm phiên hiện
  tại. Mã cần ít nhất 61 phiên để có giá trị này.
- `net_5d_ratio` = tổng giá trị nước ngoài mua ròng 5 phiên gần nhất chia
  `5 × ADV20` (ADV20 là giá trị giao dịch trung bình 20 phiên; ngày không có dòng
  OHLC tính bằng 0). Âm là bán ròng. Dòng khối ngoại thiếu giá trị mua hoặc bán bị
  bỏ qua; mã không đủ dữ liệu hoặc có ADV20 bằng 0 thì không có giá trị và không
  vào cảnh báo `foreign_out`.
- `room_missing` là room còn lại, room tổng hoặc cả hai không thể xác định sau
  bước điền dữ liệu hợp lệ gần nhất.