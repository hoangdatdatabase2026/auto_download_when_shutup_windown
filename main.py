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

LOGIN_URL = "http://103.149.99.95:8011/Account/Login"
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

ERP_USERNAME = os.environ.get("ERP_USERNAME") or "HD01566"
ERP_PASSWORD = os.environ.get("ERP_PASSWORD") or "8UIa8&!v"

GDRIVE_RAW_INPUT = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")

def get_clean_folder_id(raw_input):
    """Tự động lọc lấy ID thư mục nếu người dùng lỡ dán cả đường link URL"""
    if not raw_input:
        return None
    if "drive.google.com" in raw_input:
        # Tách lấy phần ID ở cuối đường link URL
        return raw_input.split("/")[-1].split("?")[0]
    return raw_input.strip()

def upload_file_to_gdrive(file_path):
    print(f"   [DRIVE] Đang chuẩn bị tải lên Google Drive: {os.path.basename(file_path)}...")
    
    clean_folder_id = get_clean_folder_id(GDRIVE_RAW_INPUT)
    
    if not clean_folder_id or not GDRIVE_JSON_STR:
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
            "parents": [clean_folder_id]
        }
        mimetype = "image/png" if file_path.endswith(".png") else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        media = MediaFileUpload(file_path, mimetype=mimetype)

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        print(f"   [DRIVE OK ✅] Đã upload thành công (Vào thư mục ID: {clean_folder_id})")
    except Exception as e:
        print(f"   [DRIVE ERR ❌] Lỗi upload Google Drive: {e}")

def run_automation():
    print("==================================================")
    print("🚀 BẮT ĐẦU TIẾN TRÌNH TỰ ĐỘNG HÓA ERP")
    print("==================================================")
    
    os.makedirs("./downloads", exist_ok=True)
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%M")

    with sync_playwright() as p:
        print("\n[BƯỚC 1] Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True, args=['--disable-blink-features=AutomationControlled'])
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        page.set_default_timeout(35000)

        # -------------------------------------------------------------
        # BƯỚC 2 & 3: ĐĂNG NHẬP
        # -------------------------------------------------------------
        print("\n[BƯỚC 2 & 3] Tiến hành đăng nhập...")
        try:
            page.goto(LOGIN_URL, wait_until="networkidle")
            time.sleep(2)

            print(f" -> Nhập Username: {ERP_USERNAME}")
            page.click("#user_name")
            page.type("#user_name", ERP_USERNAME, delay=100)

            print(" -> Nhập Password...")
            page.click("#pass_word")
            page.type("#pass_word", ERP_PASSWORD, delay=100)
            time.sleep(1)

            print(" -> Bấm nút ĐĂNG NHẬP...")
            page.click("button:has-text('ĐĂNG NHẬP')")
            page.press("#pass_word", "Enter")
            
            print(" -> Đang chờ xác thực (8 giây)...")
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
                page.type(input_selector, code, delay=50)
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
