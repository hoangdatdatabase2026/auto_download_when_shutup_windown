import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

ERP_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

def run_automation():
    # Luôn tạo trước thư mục downloads để tránh lỗi Artifacts của GitHub Actions
    os.makedirs("./downloads", exist_ok=True)
    
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%S")

    with sync_playwright() as p:
        print("1. Đang khởi chạy trình duyệt...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        
        # Đặt thời gian chờ tối đa cho mỗi thao tác là 60 giây (tránh timeout mạng chậm)
        page.set_default_timeout(60000)

        try:
            print(f"2. Đang mở trang đăng nhập ERP: {ERP_URL}")
            page.goto(ERP_URL, wait_until="networkidle")
            
            page.fill("id=user_name", ERP_USERNAME)
            page.fill("id=pass_word", ERP_PASSWORD)
            
            print("3. Đang bấm Đăng nhập...")
            page.click("xpath=/html/body/div[3]/div[2]/div/div/form/button")
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            print("-> Đăng nhập thành công!")
        except Exception as e:
            print(f"❌ LỖI ĐĂNG NHẬP: {e}")
            browser.close()
            return

        # Vòng lặp tải từng kho
        for wh in WAREHOUSES:
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n--- ĐANG XỬ LÝ KHO: {code.upper()} ---")
            try:
                page.goto(REPORT_URL, wait_until="networkidle")
                time.sleep(2)

                # Nhập mã kho
                input_selector = "xpath=//*[@id='ma_kho']/itg-tags-input/div/div/tags-input/div/div/input"
                page.fill(input_selector, code)
                page.click("xpath=//*[@id='ma_kho']/itg-tags-input/div/div/div/i")
                time.sleep(2)

                # Tìm kiếm
                print(" -> Bấm Tìm kiếm...")
                page.click("xpath=//*[@id='search']/span")
                time.sleep(5)

                # Mở menu Export
                print(" -> Mở menu Export Excel...")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
                page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

                # Điền tên file
                page.fill("id=fileName_ctrl", file_name_val)
                time.sleep(1)

                # Bấm xác nhận tải về
                print(f" -> Tải file: {file_name_val}")
                with page.expect_download(timeout=60000) as download_info:
                    page.click("xpath=/html/body/div[1]/div/div/div/div[3]/button[1]")
                
                download = download_info.value
                save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
                download.save_as(save_path)
                print(f" ✅ TẢI THÀNH CÔNG: {save_path}")

            except Exception as ex:
                print(f" ❌ LỖI KHI XỬ LÝ KHO {code.upper()}: {ex}")
                continue

        browser.close()
        print("\n=== HOÀN THÀNH TIẾN TRÌNH ===")

if __name__ == "__main__":
    run_automation()
