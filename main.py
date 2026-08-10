import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

LOGIN_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")

def upload_file_to_gdrive(file_path):
    """Tự động tải file Excel hoặc ảnh chụp lỗi lên Google Drive"""
    if not GDRIVE_FOLDER_ID or not GDRIVE_JSON_STR:
        print(" ⚠️ Chưa cấu hình Google Drive Secrets, bỏ qua upload.")
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
        print(f" ☁️ [Google Drive] Đã upload: {os.path.basename(file_path)}")
    except Exception as e:
        print(f" ❌ Lỗi upload Google Drive: {e}")

def run_automation():
    os.makedirs("./downloads", exist_ok=True)
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%S")

    with sync_playwright() as p:
        print("1. Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # -------------------------------------------------------------
        # BƯỚC 1: ĐĂNG NHẬP
        # -------------------------------------------------------------
        try:
            print(f"2. Truy cập trang đăng nhập: {LOGIN_URL}")
            # wait_until="domcontentloaded" để không bị treo ở trang login
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            
            page.wait_for_selector("id=user_name")
            page.fill("id=user_name", ERP_USERNAME)
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print("3. Bấm Đăng nhập (Enter)...")
            page.press("id=pass_word", "Enter")
            
            # Chờ 4 giây để hệ thống thiết lập Session
            time.sleep(4)
            print(" -> Đã gửi thông tin đăng nhập!")
        except Exception as e:
            print(f"❌ LỖI ĐĂNG NHẬP: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 2: CHUYỂN TỚI TRANG BÁO CÁO (Dùng wait_until="commit")
        # -------------------------------------------------------------
        try:
            print(f"4. Chuyển hướng tới trang Báo cáo: {REPORT_URL}")
            # Dùng wait_until="commit" để bỏ qua việc chờ load ngầm vô tận
            page.goto(REPORT_URL, wait_until="commit")
            
            # Chờ đúng ô nhập kho xuất hiện trên màn hình
            print(" -> Đang chờ giao diện Báo cáo nạp...")
            page.wait_for_selector("#ma_kho input", timeout=30000)
            print(" -> Đã mở thành công trang Báo cáo!")
        except Exception as e:
            print(f"❌ LỖI MỞ TRANG BÁO CÁO: {e}")
            page.screenshot(path="./downloads/error_report_page.png")
            upload_file_to_gdrive("./downloads/error_report_page.png")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 3: ĐIỀN TÊN KHO VÀ TẢI TỪNG BÁO CÁO
        # -------------------------------------------------------------
        for wh in WAREHOUSES:
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n==========================================")
            print(f"⚡ ĐANG XỬ LÝ KHO: {code.upper()}")
            print(f"==========================================")
            try:
                # Đảm bảo đang ở trang báo cáo
                if "SOBCTonKhaDung" not in page.url:
                    page.goto(REPORT_URL, wait_until="commit")
                    time.sleep(2)

                # 1. Tìm và điền mã kho
                input_selector = "#ma_kho input"
                page.wait_for_selector(input_selector, state="visible", timeout=15000)
                
                print(f" -> Điền mã kho: {code}")
                page.fill(input_selector, code)
                time.sleep(1)
                
                # 2. Bấm icon chọn kho
                page.click("#ma_kho i")
                time.sleep(1)

                # 3. Bấm nút Tìm kiếm
                print(" -> Bấm Tìm kiếm...")
                page.click("xpath=//*[@id='search']/span")
                time.sleep(4)

                # 4. Mở menu Export Excel
                print(" -> Mở menu Export...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # 5. Nhập tên file
                print(f" -> Đặt tên file: {file_name_val}")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # 6. Bấm nút Tải về trong Popup Modal
                print(" -> Bấm Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" ✅ Đã tải thành công: {file_name_val}.xlsx")

                # Upload trực tiếp lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" ❌ Lỗi khi xử lý kho {code.upper()}: {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    upload_file_to_gdrive(err_img)
                except:
                    pass
                continue

        browser.close()
        print("\n=== HOÀN THÀNH TẤT CẢ ===")

if __name__ == "__main__":
    run_automation()
