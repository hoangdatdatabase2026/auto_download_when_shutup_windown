import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# -------------------------------------------------------------
# CẤU HÌNH DANH SÁCH KHO VÀ THÔNG TIN TÀI KHOẢN
# -------------------------------------------------------------
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

LOGIN_URL = "http://103.149.99.95:8011/Account/Login"
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

# Đặt cứng tài khoản/mật khẩu để đảm bảo không bị rỗng do GitHub Secrets
ERP_USERNAME = os.environ.get("ERP_USERNAME") or "HD01566"
ERP_PASSWORD = os.environ.get("ERP_PASSWORD") or "8UIa8&!v"

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")

def upload_file_to_gdrive(file_path):
    """Tự động tải file Excel hoặc ảnh lỗi lên Google Drive"""
    print(f"   [DRIVE] Đang chuẩn bị tải lên Google Drive: {os.path.basename(file_path)}...")
    if not GDRIVE_FOLDER_ID or not GDRIVE_JSON_STR:
        print("   [DRIVE ⚠️] Chưa cấu hình Google Drive Secrets, bỏ qua upload.")
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

def run_automation():
    print("==================================================")
    print("🚀 BẮT ĐẦU TIẾN TRÌNH TỰ ĐỘNG HÓA ERP")
    print("==================================================")
    
    os.makedirs("./downloads", exist_ok=True)
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%M")
    print(f"[THỜI GIAN] Timestamp: {current_date_time}")

    with sync_playwright() as p:
        print("\n[BƯỚC 1] Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.set_default_timeout(35000)

        # -------------------------------------------------------------
        # BƯỚC 2 & 3: ĐĂNG NHẬP CHUẨN ĐÃ FIX Ô NHẬP TEXT
        # -------------------------------------------------------------
        print("\n[BƯỚC 2 & 3] Tiến hành đăng nhập...")
        try:
            print(f" -> Mở trang Đăng nhập: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(2)

            print(f" -> Điền Tên đăng nhập: {ERP_USERNAME}")
            user_input = page.wait_for_selector("#user_name", state="visible")
            user_input.click()
            user_input.fill(ERP_USERNAME)
            user_input.dispatch_event("input")
            user_input.dispatch_event("change")

            print(" -> Điền Mật khẩu...")
            pass_input = page.wait_for_selector("#pass_word", state="visible")
            pass_input.click()
            pass_input.fill(ERP_PASSWORD)
            pass_input.dispatch_event("input")
            pass_input.dispatch_event("change")
            time.sleep(1)

            print(" -> Bấm nút ĐĂNG NHẬP...")
            page.click("button:has-text('ĐĂNG NHẬP'), button[type='submit'], .btn-primary")
            
            print(" -> Đang chờ xác thực phiên làm việc (8 giây)...")
            time.sleep(8)

            if "Account/Login" in page.url or "Login" in page.url:
                print(f"\n❌ [LỖI ĐĂNG NHẬP] Vẫn ở trang Login: {page.url}")
                page.screenshot(path="./downloads/error_login.png")
                upload_file_to_gdrive("./downloads/error_login.png")
                browser.close()
                return
            else:
                print(f" -> [OK ✅] ĐĂNG NHẬP THÀNH CÔNG! Đã vào: {page.url}")

        except Exception as e:
            print(f" -> [LỖI ❌] SỰ CỐ ĐĂNG NHẬP: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 5: CHUYỂN TỚI TRANG BÁO CÁO
        # -------------------------------------------------------------
        print("\n[BƯỚC 5] Chuyển tới Báo cáo Tồn khả dụng...")
        page.goto(REPORT_URL, wait_until="domcontentloaded")
        time.sleep(3)

        # -------------------------------------------------------------
        # BƯỚC 6 & 7: VÒNG LẶP XỬ LÝ 6 KHO
        # -------------------------------------------------------------
        print("\n==================================================")
        print("🔄 BẮT ĐẦU VÒNG LẶP XỬ LÝ 6 KHO")
        print("==================================================")

        for idx, wh in enumerate(WAREHOUSES, 1):
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n--- [{idx}/6] ĐANG XỬ LÝ KHO: {code.upper()} ---")
            try:
                if idx > 1:
                    page.goto(REPORT_URL, wait_until="domcontentloaded")
                    time.sleep(2)

                input_selector = "xpath=//*[@id='ma_kho']//input"
                page.wait_for_selector(input_selector, state="visible", timeout=25000)
                
                page.click(input_selector)
                page.fill(input_selector, "")
                page.fill(input_selector, code)
                time.sleep(1)
                
                page.click("xpath=//*[@id='ma_kho']//i")
                time.sleep(1)

                page.click("xpath=//*[@id='search']/span")
                time.sleep(4)

                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" -> [OK ✅] Tải thành công: {file_name_val}.xlsx")

                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" -> [LỖI KHO {code.upper()} ❌] {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    upload_file_to_gdrive(err_img)
                except:
                    pass
                continue

        browser.close()
        print("\n🎉 HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH!")

if __name__ == "__main__":
    run_automation()
