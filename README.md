# Liquidity Radar – Ra-đa rủi ro thanh khoản HOSE (mở rộng HNX)

Ứng dụng Streamlit phân tích rủi ro thanh khoản cổ phiếu niêm yết trên HOSE (mở rộng
sang HNX) bằng dữ liệu cuối ngày từ SSI FastConnect. Dữ liệu được lưu cục bộ trong
SQLite, hiển thị trực quan và có thể tải về dạng CSV.

> Công cụ mang tính phân tích và học thuật; không phải khuyến nghị đầu tư.

## Nguyên tắc và giới hạn

- Chỉ dùng API dữ liệu (REST) của SSI để đọc dữ liệu cuối ngày. Không gọi API giao
  dịch, OTP hay đặt lệnh; không phát sinh giao dịch thật. Khóa API nên được cấp
  quyền chỉ đọc.
- Không dùng học máy, không có robot giao dịch, không tự động mua/bán.
- Mọi chỉ số (Amihud, ADV, số phiên thoát vị thế, xếp hạng phân vị, z-score) được
  tính bằng công thức thống kê/tài chính tường minh.
- Dữ liệu cuối ngày, không phải giá thời gian thực; ứng dụng không chạy nền.
- Chưa bao gồm sàn UPCoM. Không dự báo giá và không đưa ra thời điểm mua/bán.
- Giá đóng cửa lấy nguyên từ SSI, mã nguồn không tự điều chỉnh. Phần lớn mã có dấu
  hiệu đã được SSI điều chỉnh theo quyền; một số ít mã giao dịch thưa có biến động
  giá lớn qua các ngày nghỉ giao dịch hoặc sự kiện quyền, có thể làm Amihud lệch
  trong cửa sổ 20 phiên liền kề.

## Tính năng

- Chấm điểm rủi ro thanh khoản 0–100 theo từng mã, xếp hạng riêng trong từng sàn
  (HOSE, HNX); các rổ VN30, VN100 là phần lọc từ hạng của HOSE.
- Theo dõi Amihud, ADV, số phiên để thoát vị thế, dòng tiền khối ngoại và room ngoại.
- Cảnh báo: khối lượng thấp/cao bất thường, khối ngoại bán ròng mạnh, room ngoại hết
  hoặc bất thường, đóng cửa giá trần/sàn, số phiên thoát vị thế vượt mốc, dữ liệu cũ,
  mã giao dịch thưa. Trang cảnh báo có thể bấm xem chi tiết từng nhóm.
- Tra nhanh theo số cổ phiếu hoặc số tiền đang nắm giữ.
- Trang chi tiết từng mã: thanh khoản theo thời gian, dòng tiền nước ngoài, giá và chỉ
  báo tham khảo (MA, RSI, MACD), sự kiện quyền và liên kết tìm tin tức.
- Cấu hình số tiền, tỷ lệ tham gia, cửa sổ quan sát, trọng số và ngưỡng cảnh báo ngay
  trong thanh bên.
- Giao diện sáng/tối, đổi màu chủ đạo, đổi kiểu chữ (mặc định Times New Roman), tải
  bảng kết quả dạng CSV.
- Tự nạp bổ sung dữ liệu mới một lần khi mở ứng dụng (tắt bằng biến môi trường
  `AUTO_UPDATE=0`) và có nút cập nhật thủ công trong thanh bên.

## Yêu cầu

- Python 3.10 trở lên
- Tài khoản SSI có `SSI_API_KEY` và `SSI_API_SECRET`
- Kết nối Internet để xác thực và nạp dữ liệu

## Cài đặt

Chạy từ thư mục gốc dự án (PowerShell):

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Mở `.env` và điền thông tin SSI:

```dotenv
SSI_API_URL=https://api.ssi.com.vn
SSI_API_KEY=ma_api_key
SSI_API_SECRET=ma_api_secret
```

Không commit `.env` hoặc đưa khóa API vào README, mã nguồn hay dữ liệu mẫu.

## Nạp dữ liệu

Mặc định nạp từ ngày `2025/01/01` đến hôm nay. Lần đầu cần chạy `--sync` để tạo danh
sách mã của rổ.

```powershell
# Lần đầu: lấy danh sách mã từ SSI rồi nạp
python -m src.data.ingest --universe hose --sync
python -m src.data.ingest --universe hnx --sync

# Các lần sau: nạp tiếp (chỉ lấy phần còn thiếu, có lùi 7 ngày để bù dữ liệu công bố muộn)
python -m src.data.ingest --universe hose
python -m src.data.ingest --universe hnx

# Rổ nhỏ hoặc một số mã cụ thể
python -m src.data.ingest --universe vn30
python -m src.data.ingest --symbols FPT,VNM,ACB

# Thử giới hạn số mã, hoặc đổi khoảng thời gian
python -m src.data.ingest --universe vn30 --limit 5
python -m src.data.ingest --universe vn30 --from 2026/01/01 --to 2026/11/21
```

| Tùy chọn | Ý nghĩa |
|---|---|
| `--universe` | `vn30`, `vn100`, `hose` hoặc `hnx` |
| `--sync` | Lấy lại danh sách mã từ SSI và ghi vào `config/universes/*.txt` |
| `--symbols` | Danh sách mã cách nhau bởi dấu phẩy; ghi đè `--universe` |
| `--limit` | Chỉ nạp số mã đầu tiên để thử |
| `--limits-days` | Số ngày lấy giá trần/sàn, mặc định `5`; đặt `0` để bỏ qua |
| `--from`, `--to` | Khoảng ngày nạp, định dạng `YYYY/MM/DD` |

Nạp toàn bộ HOSE hoặc HNX mất vài phút đến vài chục phút (mỗi mã gọi API hai lần). Mã
lỗi được in ra cuối đợt và có thể chạy lại bằng `--symbols`.

Nạp lịch sử sự kiện quyền (chia thành các đoạn 5 ngày theo giới hạn của SSI):

```powershell
python -m src.data.ingest_actions --days 365
```

## Chạy ứng dụng

```powershell
streamlit run src/app/streamlit_app.py
```

Mở địa chỉ Streamlit hiển thị trên terminal, thường là `http://localhost:8501`. Ứng dụng
đọc cơ sở dữ liệu `data/liquidity.db`; nếu chưa có dữ liệu, hãy nạp ít nhất một rổ trước.

## Chạy thử không cần khóa SSI

Repo có DB mẫu gồm toàn bộ HOSE và HNX, chỉ giữ khoảng 6 tháng gần nhất (điểm số các
mã giống DB đầy đủ):
Cần tạo môi trường ảo và cài thư viện như mục Cài đặt (bỏ qua bước tạo `.env`).

```powershell
New-Item -ItemType Directory -Force data
Copy-Item data_sample\liquidity_sample.db data\liquidity.db
$env:AUTO_UPDATE="0"
streamlit run src/app/streamlit_app.py
```

## Cách tính điểm

Điểm là trung bình có trọng số của hai thứ hạng phân vị **trong cùng sàn**:

- **Amihud:** trung bình `|lợi suất ngày| / giá trị giao dịch (tỷ đồng)`, cửa sổ mặc
  định 20 phiên, cần tối thiểu 10 ngày có giao dịch.
- **Số phiên thoát vị thế:** `giá trị cần bán / (tỷ lệ tham gia × ADV)`; mặc định 50 tỷ
  đồng, tỷ lệ tham gia 20%, ADV 20 phiên.

```text
Điểm = 50% × hạng Amihud + 50% × hạng số phiên thoát vị thế
```

Càng cao, mã càng khó mua/bán tương đối so với các mã cùng sàn. Điểm là thứ hạng tương
đối, không phải xác suất hay khuyến nghị.

- Mức `Cao`, `Trung bình`, `Thấp` chia theo tam phân vị của điểm trong sàn.
- Mã có điểm nhưng giao dịch dưới 10 ngày trong cửa sổ gần nhất luôn xếp `Cao`.
- Mã không có điểm (không giao dịch trong cửa sổ, hoặc mới niêm yết chưa đủ dữ liệu)
  hiển thị `Thiếu dữ liệu`.
- Mã có dưới 61 phiên không đủ điều kiện tính z-score khối lượng 60 phiên.
- Các cảnh báo (khối ngoại, khối lượng, trần/sàn, room) tách khỏi điểm rủi ro.

Lưu ý khi xem HNX: số tiền mặc định 50 tỷ đồng phù hợp HOSE; HNX giao dịch nhỏ hơn
nhiều nên cảnh báo "số phiên thoát vị thế vượt mốc" sẽ xuất hiện ở hầu hết mã. Nên giảm
số tiền trong thanh bên khi xem HNX.

## Cấu trúc dự án

```text
liquidity-radar-vn30/
├── config/universes/       Danh sách mã VN30, VN100, HOSE, HNX (*.txt)
├── data/                   SQLite (data/liquidity.db), tạo khi nạp dữ liệu
├── data_sample/            DB mẫu HOSE + HNX (khoảng 6 tháng gần nhất) để chạy thử
├── docs/                   Từ điển dữ liệu
├── src/
│   ├── analytics/          Chấm điểm, phân mức, kiểm tra độ ổn định
│   ├── app/                Giao diện Streamlit
│   ├── data/               Danh mục mã, nạp dữ liệu, SQLite
│   ├── finance/            Chỉ số thanh khoản và dòng tiền nước ngoài
│   └── ssi_api/            Xác thực và gọi API SSI (chỉ đọc dữ liệu)
├── check/                  Script kiểm tra dữ liệu, độ phủ, trần/sàn, room, xếp hạng
├── tests/                  Bộ kiểm thử pytest
├── probe.py                Thăm dò API dữ liệu SSI
└── requirements.txt
```

Chi tiết bảng, cột và cách xử lý dữ liệu nằm trong
[từ điển dữ liệu](docs/data_dictionary.md).

## Kiểm thử

```powershell
python -m pytest
```

Các nhóm kiểm thử: `test_liquidity.py`, `test_scoring.py`,
`test_scoring_room_limits.py`, `test_scoring_sessions_exchange.py`, `test_store.py`,
`test_client.py`.

## Kiểm tra dữ liệu

```powershell
python -m check.check_db
python -m check.check_coverage
python -m check.check_limits
python -m check.check_room
python -m check.check_universe
```

## Dữ liệu và quyền riêng tư

- `.env` và các tệp `*.db` được liệt kê trong `.gitignore`; không chia sẻ khóa API.
- Dữ liệu thị trường là dữ liệu đầu ra của API SSI; quyền sử dụng tuân theo điều khoản
  và gói truy cập SSI của người dùng.