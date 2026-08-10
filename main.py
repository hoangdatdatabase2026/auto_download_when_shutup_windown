import os
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# -------------------------------------------------------------
# CẤU HÌNH DANH SÁCH KHO VÀ ĐƯỜNG DẪN ERP
# -------------------------------------------------------------
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

LOGIN_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")

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
    print(f"[THỜI GIAN] Format timestamp tạo file: {current_date_time}")

    with sync_playwright() as p:
        print("\n[BƯỚC 1] Khởi chạy trình duyệt Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            accept_downloads=True, 
            viewport={"width": 1366, "height": 768}
        )
        page = context.new_page()
        page.set_default_timeout(30000)

        # -------------------------------------------------------------
        # BƯỚC 1, 2 & 3: ĐĂNG NHẬP VÀ XÁC THỰC
        # -------------------------------------------------------------
        print("\n[BƯỚC 2 & 3] Tiến hành đăng nhập hệ thống ERP...")
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.wait_for_selector("id=user_name")
            page.fill("id=user_name", ERP_USERNAME)
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print(" -> Click nút Đăng nhập...")
            page.click("xpath=/html/body/div[3]/div[2]/div/div/form/button")
            
            # Chờ Menu Sidebar xuất hiện -> Khẳng định 100% đã vào được trang chủ ERP
            print(" -> Đang chờ giao diện chính ERP (#sidebar) nạp xong...")
            page.wait_for_selector("#sidebar", timeout=30000)
            print(f" -> [OK ✅] ĐĂNG NHẬP THÀNH CÔNG! URL hiện tại: {page.url}")
            time.sleep(2)
        except Exception as e:
            print(f" -> [LỖI ❌] Không vào được trang chủ ERP (#sidebar không xuất hiện). URL hiện tại: {page.url}")
            print(f" -> Chi tiết lỗi: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 5: CHUYỂN TRANG BÁO CÁO NỘI BỘ QUA JS ROUTER (KHÔNG RELOAD)
        # -------------------------------------------------------------
        print("\n[BƯỚC 5] Chuyển tới Báo cáo Tồn khả dụng (JS Internal Router)...")
        try:
            # Đổi Hash nội bộ để AngularJS tự load View mà không bị mất Session
            page.evaluate("window.location.hash = '#/SO/Report/SOBCTonKhaDung'")
            time.sleep(3)
            
            # Chờ thẻ chọn kho #ma_kho thực sự xuất hiện trên màn hình
            print(" -> Đang chờ ô chọn kho (#ma_kho) nạp vào màn hình...")
            page.wait_for_selector("#ma_kho", state="visible", timeout=30000)
            print(" -> [OK ✅] Đã nạp thành công giao diện Báo cáo!")
        except Exception as e:
            print(f" -> [LỖI ❌] Không nạp được màn hình Báo cáo: {e}")
            page.screenshot(path="./downloads/error_report_page.png")
            upload_file_to_gdrive("./downloads/error_report_page.png")
            browser.close()
            return

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
                # Chuyển Route qua JS nếu từ kho thứ 2 trở đi
                if idx > 1:
                    page.evaluate("window.location.hash = '#/SO/Report/SOBCTonKhaDung'")
                    time.sleep(2)

                # BƯỚC 6: Điền mã kho vào ô tag input
                input_selector = "xpath=//*[@id='ma_kho']//input"
                page.wait_for_selector(input_selector, state="visible", timeout=20000)
                
                # Xóa dữ liệu cũ và điền mã kho mới
                page.fill(input_selector, "")
                time.sleep(0.5)
                page.fill(input_selector, code)
                time.sleep(1)
                
                # Bấm icon chọn kho
                page.click("xpath=//*[@id='ma_kho']//i")
                time.sleep(1)

                # Bấm Xem báo cáo / Tìm kiếm
                print(" -> Bấm Xem báo cáo (Search)...")
                page.click("xpath=//*[@id='search']/span")
                time.sleep(4)

                # BƯỚC 7: Xuất file Excel
                print(" -> Thao tác mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # Điền tên file
                print(f" -> Điền tên file: '{file_name_val}'")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # Bấm Tải về trong Modal
                print(" -> Bấm nút Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" -> [OK ✅] Tải thành công: {file_name_val}.xlsx")

                # Upload trực tiếp lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" -> [LỖI KHO {code.upper()} ❌] {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    print(f" -> Đã lưu ảnh chụp màn hình lỗi: {err_img}")
                    upload_file_to_gdrive(err_img)
                except:
                    pass
                continue

        browser.close()
        print("\n==================================================")
        print("🎉 HOÀN THÀNH TẤT CẢ CÁC BƯỚC TỰ ĐỘNG HÓA!")
        print("==================================================")

if __name__ == "__main__":
    run_automation()
