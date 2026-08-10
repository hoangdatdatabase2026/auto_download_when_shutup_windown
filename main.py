import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Danh sách 6 kho và tiền tố tên file tương ứng
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

# BƯỚC 1: Khai báo đường dẫn trang Đăng nhập và Báo cáo đích
LOGIN_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

# BƯỚC 2: Tài khoản & Mật khẩu
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")

GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")

def upload_file_to_gdrive(file_path):
    """Tự động tải file Excel hoặc ảnh lỗi lên Google Drive"""
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
    
    # BƯỚC 4: Tạo giá trị ngày giờ hiện tại theo format dd.mm.yyyy HHmm
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%M")
    print(f"-> Định dạng thời gian tạo file: {current_date_time}")

    with sync_playwright() as p:
        print("1. Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.set_default_timeout(35000)

        # BƯỚC 1, 2 & 3: ĐĂNG NHẬP ERP
        try:
            print(f"2. Truy cập trang đăng nhập: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            
            page.wait_for_selector("id=user_name")
            page.fill("id=user_name", ERP_USERNAME)
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print("3. Bấm Đăng nhập...")
            page.click("xpath=/html/body/div[3]/div[2]/div/div/form/button")
            time.sleep(4)
            print(" -> Đăng nhập thành công!")
        except Exception as e:
            print(f"❌ LỖI ĐĂNG NHẬP: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # BƯỚC 5: TRUY CẬP TRANG BÁO CÁO TỒN KHẢ DỤNG
        try:
            print(f"5. Chuyển hướng tới vị trí lấy dữ liệu: {REPORT_URL}")
            page.goto(REPORT_URL, wait_until="domcontentloaded")
            time.sleep(3)
            
            # Thử thao tác Click Sidebar (Kho vận -> Báo cáo -> Báo cáo tồn khả dụng)
            try:
                page.click("xpath=//*[@id='sidebar']/div/ul/li[5]/a", timeout=3000)
                time.sleep(1)
                page.click("xpath=//*[@id='sidebar']/div/ul/li[5]/ul/li[7]/a", timeout=3000)
                time.sleep(1)
                page.click("xpath=//*[@id='sidebar']/div/ul/li[5]/ul/li[7]/ul/li[10]/a", timeout=3000)
                time.sleep(2)
            except:
                pass
        except Exception as e:
            print(f"⚠️ Lỗi điều hướng báo cáo: {e}")

        # BƯỚC 6 & 7: LẶP QUA TỪNG KHO VÀ TẢI EXCEL
        for wh in WAREHOUSES:
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n==========================================")
            print(f"⚡ BƯỚC 6 & 7: XỬ LÝ KHO: {code.upper()}")
            print(f"==========================================")
            try:
                # Mở trang báo cáo mới cho mỗi vòng lặp
                page.goto(REPORT_URL, wait_until="domcontentloaded")
                time.sleep(2)

                # BƯỚC 6: Điền tên kho vào ô Lookup / Tag input
                input_selector = "xpath=//*[@id='ma_kho']/itg-tags-input/div/div/tags-input/div/div/input"
                page.wait_for_selector(input_selector, state="visible", timeout=20000)
                
                print(f" -> Điền mã kho: {code}")
                page.fill(input_selector, code)
                time.sleep(1)
                
                # Bấm icon xác nhận kho
                page.click("xpath=//*[@id='ma_kho']/itg-tags-input/div/div/div/i")
                time.sleep(1)

                # Bấm Xem báo cáo / Tìm kiếm
                print(" -> Bấm Xem báo cáo (Search)...")
                page.click("xpath=//*[@id='search']/span")
                time.sleep(4)

                # BƯỚC 7: Xuất Excel
                print(" -> Mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # Điền tên file theo chuẩn (Ví dụ: tkkd_da 10.08.2026 1102)
                print(f" -> Điền tên file: {file_name_val}")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # Bấm xác nhận Tải về
                print(" -> Bấm Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" ✅ Đã tải file: {file_name_val}.xlsx")

                # Tải file trực tiếp lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" ❌ Lỗi xử lý kho {code.upper()}: {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    upload_file_to_gdrive(err_img)
                except:
                    pass
                continue

        browser.close()
        print("\n=== HOÀN THÀNH TOÀN BỘ TIẾN TRÌNH ===")

if __name__ == "__main__":
    run_automation()
