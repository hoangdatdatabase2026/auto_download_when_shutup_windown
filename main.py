import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Danh sách 6 kho cần tải
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
    """Đẩy trực tiếp từng file Excel lên Google Drive ngay khi tải xong"""
    if not GDRIVE_FOLDER_ID or not GDRIVE_JSON_STR:
        print(" ⚠️ Chưa cấu hình Google Drive Secrets, bỏ qua bước upload.")
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
        media = MediaFileUpload(file_path, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id"
        ).execute()
        print(f" ☁️ [Google Drive] Đã upload thành công: {os.path.basename(file_path)} (ID: {uploaded_file.get('id')})")
    except Exception as e:
        print(f" ❌ Lỗi upload Google Drive: {e}")

def run_automation():
    os.makedirs("./downloads", exist_ok=True)
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%S")

    with sync_playwright() as p:
        print("1. Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        
        # Đặt kích thước màn hình chuẩn Desktop để không bị ẩn các menu responsive
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        page.set_default_timeout(45000)

        # -------------------------------------------------------------
        # BƯỚC 1: ĐĂNG NHẬP
        # -------------------------------------------------------------
        try:
            print(f"2. Đang truy cập trang đăng nhập: {LOGIN_URL}")
            page.goto(LOGIN_URL)
            
            page.wait_for_selector("id=user_name")
            page.fill("id=user_name", ERP_USERNAME)
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print("3. Đang bấm nút Đăng nhập...")
            page.click("xpath=/html/body/div[3]/div[2]/div/div/form/button")
            
            # Chờ 5s để hệ thống khởi tạo Session đăng nhập
            time.sleep(5)
            print(" -> Đăng nhập thành công!")
        except Exception as e:
            print(f"❌ LỖI TRONG QUÁ TRÌNH ĐĂNG NHẬP: {e}")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 2: CHUYỂN HƯỚNG THẲNG TỚI LINK BÁO CÁO CỤ THỂ
        # -------------------------------------------------------------
        try:
            print(f"4. Đang truy cập link báo cáo: {REPORT_URL}")
            page.goto(REPORT_URL)
            time.sleep(3)
        except Exception as e:
            print(f"❌ LỖI KHI MỞ LINK BÁO CÁO: {e}")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 3: XỬ LÝ TỪNG KHO VÀ TẢI BÁO CÁO
        # -------------------------------------------------------------
        for wh in WAREHOUSES:
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n==========================================")
            print(f"⚡ ĐANG XỬ LÝ KHO: {code.upper()}")
            print(f"==========================================")
            try:
                # Đảm bảo trình duyệt luôn ở đúng URL Báo cáo
                if page.url != REPORT_URL:
                    page.goto(REPORT_URL)
                    time.sleep(2)

                # 1. Nhập mã kho vào ô tag input
                input_selector = "xpath=//*[@id='ma_kho']/itg-tags-input/div/div/tags-input/div/div/input"
                print(" -> Đang chờ ô nhập mã kho...")
                page.wait_for_selector(input_selector, state="visible")
                
                print(f" -> Nhập mã kho: {code}")
                page.fill(input_selector, code)
                time.sleep(1)
                
                # 2. Bấm icon thêm kho
                print(" -> Bấm icon xác nhận kho...")
                page.click("xpath=//*[@id='ma_kho']/itg-tags-input/div/div/div/i")
                time.sleep(1)

                # 3. Bấm nút Tìm kiếm
                search_btn = "xpath=//*[@id='search']/span"
                print(" -> Bấm nút Tìm kiếm...")
                page.wait_for_selector(search_btn)
                page.click(search_btn)
                print(" -> Đang chờ bảng dữ liệu tải...")
                time.sleep(4)

                # 4. Thao tác mở Menu Export Excel
                print(" -> Mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # 5. Điền tên file
                print(f" -> Nhập tên file: {file_name_val}")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # 6. Bấm nút xác nhận tải trong Popup Modal
                print(" -> Bấm nút Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=45000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" ✅ Đã tải file Excel về máy chủ: {file_name_val}.xlsx")

                # 7. Đẩy file trực tiếp lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" ❌ Lỗi khi xử lý kho {code.upper()}: {ex}")
                # Nếu bị lỗi giữa chừng, reload lại trang báo cáo để làm tiếp kho sau
                try:
                    page.goto(REPORT_URL)
                    time.sleep(3)
                except:
                    pass
                continue

        browser.close()
        print("\n=== HOÀN THÀNH TẤT CẢ CÁC KHO ===")

if __name__ == "__main__":
    run_automation()
