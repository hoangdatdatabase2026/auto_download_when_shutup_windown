import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==============================================================================
# PHẦN 1: CẤU HÌNH DANH SÁCH KHO VÀ ĐƯỜNG DẪN HỆ THỐNG
# ==============================================================================
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

# Đường dẫn trang Đăng nhập và Báo cáo Tồn khả dụng
LOGIN_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

# Đọc tài khoản từ GitHub Secrets (hoặc dùng mặc định nếu chưa cài)
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")

# Đọc cấu hình Google Drive từ GitHub Secrets
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")


# ==============================================================================
# PHẦN 2: HÀM UPLOAD FILE TRỰC TIẾP LÊN GOOGLE DRIVE
# ==============================================================================
def upload_file_to_gdrive(file_path):
    """
    LOGIC: Kiểm tra cấu hình Secrets -> Đăng thực thể Service Account -> Tải file lên Drive.
    """
    print(f"   [DRIVE] Chuẩn bị đẩy file: {os.path.basename(file_path)}...")
    if not GDRIVE_FOLDER_ID or not GDRIVE_JSON_STR:
        print("   [DRIVE ⚠️] Chưa cấu hình Google Drive Secrets trên GitHub, bỏ qua bước upload.")
        return
    try:
        creds_dict = json.loads(GDRIVE_JSON_STR)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/drive.file"]
        )
        service = build("drive", "v3", credentials=creds)

        file_metadata = {
            "name": os.path.basename(file_path),
            "parents": [GDRIVE_FOLDER_ID]
        }
        mimetype = "image/png" if file_path.endswith(".png") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        media = MediaFileUpload(file_path, mimetype=mimetype)

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        print(f"   [DRIVE OK ✅] Đã upload thành công (ID: {uploaded_file.get('id')})")
    except Exception as e:
        print(f"   [DRIVE ERR ❌] Lỗi upload Google Drive: {e}")


# ==============================================================================
# PHẦN 3: LUỒNG TỰ ĐỘNG HÓA CHÍNH (PLAYWRIGHT)
# ==============================================================================
def run_automation():
    print("==================================================")
    print("🚀 BẮT ĐẦU TIẾN TRÌNH TỰ ĐỘNG HÓA ERP")
    print("==================================================")
    
    os.makedirs("./downloads", exist_ok=True)
    
    # Định dạng timestamp theo đúng yêu cầu: dd.mm.yyyy HHMM
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%M")
    print(f"[THỜI GIAN] Format timestamp tạo file: {current_date_time}")

    with sync_playwright() as p:
        # LOGIC: Khởi tạo trình duyệt Chromium ẩn với độ phân giải chuẩn Desktop
        print("\n[BƯỚC 1] Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.set_default_timeout(35000)
        print(" -> [OK] Trình duyệt đã sẵn sàng.")

        # ----------------------------------------------------------------------
        # LOGIC ĐĂNG NHẬP (BƯỚC 2 & 3):
        # 1. Truy cập trang LOGIN_URL và chờ Form load xong.
        # 2. Điền Username & Password vào ô tương ứng.
        # 3. Kích hoạt Submit bằng cách Click nút ĐĂNG NHẬP + Nhấn phím Enter.
        # 4. Kiểm tra xem URL có chuyển hướng sang trang ERP nội bộ hay không.
        # ----------------------------------------------------------------------
        print("\n[BƯỚC 2 & 3] Tiến hành đăng nhập hệ thống ERP...")
        try:
            print(f" -> Mở trang Đăng nhập: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            print(f" -> Điền Tên đăng nhập: {ERP_USERNAME}")
            page.wait_for_selector("#user_name", state="visible")
            page.fill("#user_name", ERP_USERNAME)
            
            print(" -> Điền Mật khẩu...")
            page.fill("#pass_word", ERP_PASSWORD)
            
            print(" -> Thực hiện Submit form Đăng nhập...")
            # Click nút bấm theo selector linh hoạt
            submit_btn = page.locator("button[type='submit'], form button, .btn-primary")
            if submit_btn.count() > 0:
                submit_btn.first.click()
            else:
                page.press("#pass_word", "Enter")
                
            time.sleep(1)
            # Nhấn thêm Enter để đảm bảo sự kiện form submit kích hoạt 100%
            page.press("#pass_word", "Enter")

            print(" -> Đang chờ hệ thống xác thực phiên đăng nhập (6s)...")
            time.sleep(6)

            # LOGIC XÁC NHẬN: Kiểm tra xem URL đã thoát khỏi trang Login chưa
            if "Account/Login" in page.url or "Login" in page.url:
                print(f" -> [LỖI ❌] Không thể Đăng nhập. Trình duyệt vẫn ở trang Login: {page.url}")
                page.screenshot(path="./downloads/error_login.png")
                upload_file_to_gdrive("./downloads/error_login.png")
                browser.close()
                return
            else:
                print(f" -> [OK ✅] ĐĂNG NHẬP THÀNH CÔNG! Đã chuyển hướng tới: {page.url}")

        except Exception as e:
            print(f" -> [LỖI ❌] ĐĂNG NHẬP GẶP SỰ CỐ: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # ----------------------------------------------------------------------
        # LOGIC MỞ TRANG BÁO CÁO (BƯỚC 5):
        # Truy cập trực tiếp URL Báo cáo Tồn khả dụng sau khi đã có Session đăng nhập.
        # ----------------------------------------------------------------------
        print("\n[BƯỚC 5] Chuyển tới Báo cáo Tồn khả dụng...")
        try:
            page.goto(REPORT_URL, wait_until="domcontentloaded")
            time.sleep(3)
            print(" -> [OK ✅] Đã tải giao diện Báo cáo.")
        except Exception as e:
            print(f" -> [CẢNH BÁO ⚠️] Lỗi nạp URL báo cáo: {e}")

        # ----------------------------------------------------------------------
        # LOGIC VÒNG LẶP LẤY BÁO CÁO 6 KHO (BƯỚC 6 & 7):
        # Lần lượt chọn mã kho -> Xem báo cáo -> Mở menu Export Excel -> Tải file -> Đẩy lên Google Drive
        # ----------------------------------------------------------------------
        print("\n==================================================")
        print("🔄 BẮT ĐẦU VÒNG LẶP XỬ LÝ 6 KHO")
        print("==================================================")

        for idx, wh in enumerate(WAREHOUSES, 1):
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n--- [{idx}/6] ĐANG XỬ LÝ KHO: {code.upper()} ---")
            try:
                # 1. Chuyển lại URL Báo cáo cho từng kho để reset form
                if idx > 1:
                    page.goto(REPORT_URL, wait_until="domcontentloaded")
                    time.sleep(2)

                # 2. Tìm ô nhập kho và điền dữ liệu
                input_selector = "xpath=//*[@id='ma_kho']//input"
                print(f" 1. Chờ ô nhập mã kho xuất hiện...")
                page.wait_for_selector(input_selector, state="visible", timeout=25000)
                
                print(f" 2. Điền mã kho: '{code}'")
                page.fill(input_selector, "")
                page.fill(input_selector, code)
                time.sleep(1)
                
                # 3. Bấm icon thêm kho vào danh sách
                print(" 3. Bấm icon chọn kho...")
                page.click("xpath=//*[@id='ma_kho']//i")
                time.sleep(1)

                # 4. Bấm Xem báo cáo / Tìm kiếm
                print(" 4. Bấm nút Xem báo cáo (Search)...")
                page.click("xpath=//*[@id='search']/span")
                time.sleep(4)

                # 5. Mở Popup Export Excel
                print(" 5. Mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # 6. Nhập tên file Excel cần lưu
                print(f" 6. Điền tên file: '{file_name_val}'")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # 7. Bấm Tải về và bắt sự kiện expect_download của Playwright
                print(" 7. Bấm nút Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                # 8. Lưu file Excel vừa tải xuống máy chủ
                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" -> [OK ✅] Tải file Excel thành công: {file_name_val}.xlsx")

                # 9. Tải file Excel vừa lấy lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" -> [LỖI KHO {code.upper()} ❌] {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    print(f" -> Đã lưu ảnh lỗi: {err_img}")
                    upload_file_to_gdrive(err_img)
                except:
                    pass
                continue

        browser.close()
        print("\n==================================================")
        print("🎉 HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH!")
        print("==================================================")

if __name__ == "__main__":
    run_automation()
