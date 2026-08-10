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
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

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
        page.set_default_timeout(35000)
        print(" -> [OK] Trình duyệt đã sẵn sàng.")

        # -------------------------------------------------------------
        # BƯỚC 1, 2 & 3: ĐĂNG NHẬP FLEXIBLE
        # -------------------------------------------------------------
        print("\n[BƯỚC 2 & 3] Tiến hành đăng nhập hệ thống ERP...")
        try:
            print(f" -> Mở trang Đăng nhập: {LOGIN_URL}")
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            print(" -> Đang điền Tên đăng nhập...")
            page.wait_for_selector("id=user_name")
            page.fill("id=user_name", ERP_USERNAME)
            
            print(" -> Đang điền Mật khẩu...")
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print(" -> Gửi yêu cầu Đăng nhập (Ấn Enter & Click)...")
            page.press("id=pass_word", "Enter")
            time.sleep(1)
            try:
                page.click("button[type='submit']", timeout=3000)
            except:
                pass
            
            print(" -> Đang chờ hệ thống khởi tạo phiên làm việc (5 giây)...")
            time.sleep(5)

            # Mở thử trang Báo cáo để xác nhận Đăng nhập thành công hay chưa
            print(" -> Kiểm tra quyền truy cập bằng cách mở trang Báo cáo...")
            page.goto(REPORT_URL, wait_until="domcontentloaded")
            time.sleep(3)

            if "Account/Login" in page.url or "Login" in page.url:
                print(f" -> [LỖI ❌] ĐĂNG NHẬP THẤT BẠI! Hệ thống bị đẩy ngược về trang Login. Hãy kiểm tra lại ERP_USERNAME và ERP_PASSWORD trên GitHub Secrets.")
                page.screenshot(path="./downloads/error_login.png")
                upload_file_to_gdrive("./downloads/error_login.png")
                browser.close()
                return
            else:
                print(f" -> [OK ✅] ĐĂNG NHẬP THÀNH CÔNG! Đã vào trang: {page.url}")

        except Exception as e:
            print(f" -> [LỖI ❌] ĐĂNG NHẬP GẶP SỰ CỐ: {e}")
            page.screenshot(path="./downloads/error_login.png")
            upload_file_to_gdrive("./downloads/error_login.png")
            browser.close()
            return

        # -------------------------------------------------------------
        # BƯỚC 6 & 7: VÒNG LẶP XỬ LÝ TỪNG KHO
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
                # 1. Mở trang báo cáo
                print(" 1. Mở lại trang Báo cáo Tồn khả dụng...")
                page.goto(REPORT_URL, wait_until="domcontentloaded")
                time.sleep(2)

                # 2. Tìm và điền mã kho
                input_selector = "xpath=//*[@id='ma_kho']//input"
                print(f" 2. Chờ ô nhập mã kho ({input_selector})...")
                page.wait_for_selector(input_selector, state="visible", timeout=25000)
                
                print(f" -> Điền chuỗi mã kho: '{code}'")
                page.fill(input_selector, code)
                time.sleep(1)
                
                # 3. Bấm icon chọn kho
                print(" 3. Bấm icon chọn kho (tag input)...")
                page.click("xpath=//*[@id='ma_kho']//i")
                time.sleep(1)
                print(" -> [OK] Đã chọn kho.")

                # 4. Bấm Xem báo cáo / Tìm kiếm
                print(" 4. Bấm nút Xem báo cáo (Search)...")
                page.click("xpath=//*[@id='search']/span")
                print(" -> Đang chờ hệ thống truy vấn dữ liệu kho...")
                time.sleep(4)
                print(" -> [OK] Đã hoàn tất tìm kiếm.")

                # 5. Mở menu Export Excel
                print(" 5. Thao tác mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                time.sleep(1)
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")
                print(" -> [OK] Đã mở Popup xuất file Excel.")

                # 6. Điền tên file
                print(f" 6. Điền tên file: '{file_name_val}'")
                page.wait_for_selector("id=fileName_ctrl", state="visible")
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # 7. Bấm nút Tải về
                print(" 7. Bấm nút xác nhận Tải về...")
                btn_ok = "xpath=/html/body/div[1]/div/div/div/div[3]/button[1]"
                page.wait_for_selector(btn_ok, state="visible")
                
                with page.expect_download(timeout=40000) as download_info:
                    page.click(btn_ok)

                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" -> [OK ✅] Đã tải file Excel về máy chủ thành công: {file_name_val}.xlsx")

                # 8. Upload lên Google Drive
                upload_file_to_gdrive(save_path)

            except Exception as ex:
                print(f" -> [LỖI KHO {code.upper()} ❌] {ex}")
                err_img = f"./downloads/error_{code}.png"
                try:
                    page.screenshot(path=err_img)
                    print(f" -> Đã chụp ảnh lỗi: {err_img}")
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
