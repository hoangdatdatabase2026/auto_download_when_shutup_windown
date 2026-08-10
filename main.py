import os
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# Danh sách 6 kho và tiền tố tên file tương ứng trong JSON của bạn
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

# Đọc tài khoản từ biến môi trường (Secrets trên GitHub) hoặc dùng mặc định từ JSON
ERP_URL = os.environ.get("ERP_URL", "http://103.149.99.95:8011/Account/Login")
ERP_USERNAME = os.environ.get("ERP_USERNAME", "HD01566")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD", "8UIa8&!v")
REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

def run_automation():
    # Tạo thư mục lưu file tải về nếu chưa có
    os.makedirs("./downloads", exist_ok=True)
    
    # Định dạng thời gian giống định dạng storeEval trong UI.Vision của bạn (dd.mm.yyyy HHSS)
    now = datetime.now()
    current_date_time = now.strftime("%d.%m.%Y %H%S")

    with sync_playwright() as p:
        # Bật trình duyệt Chromium (headless=True để chạy ẩn trên GitHub Actions)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # ------------------------------------------------------------------
        # 1. ĐĂNG NHẬP
        # ------------------------------------------------------------------
        print("1. Đang mở trang đăng nhập ERP...")
        page.goto(ERP_URL)
        
        page.click("id=user_name")
        page.fill("id=user_name", ERP_USERNAME)
        page.fill("id=pass_word", ERP_PASSWORD)
        
        # Bấm nút đăng nhập
        print("2. Đang đăng nhập...")
        page.click("xpath=/html/body/div[3]/div[2]/div/div/form/button")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # ------------------------------------------------------------------
        # 2. VÒNG LẶP TẢI BÁO CÁO CHO TỪNG KHO
        # ------------------------------------------------------------------
        for wh in WAREHOUSES:
            code = wh["code"]
            prefix = wh["prefix"]
            file_name_val = f"{prefix} {current_date_time}"

            print(f"\n--- ĐANG XỬ LÝ KHO: {code.upper()} ---")
            
            # Mở trang báo cáo
            page.goto(REPORT_URL)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # Nhập mã kho vào ô tag input
            input_selector = "xpath=//*[@id='ma_kho']/itg-tags-input/div/div/tags-input/div/div/input"
            page.fill(input_selector, code)
            
            # Bấm icon xác nhận chọn kho
            page.click("xpath=//*[@id='ma_kho']/itg-tags-input/div/div/div/i")
            time.sleep(2)

            # Bấm nút Tìm kiếm (Search)
            print(" -> Đang bấm Tìm kiếm...")
            page.click("xpath=//*[@id='search']/span")
            time.sleep(5)  # Chờ bảng dữ liệu tải

            # Bấm Menu Xuất Excel
            print(" -> Đang mở menu Export...")
            page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/a")
            page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/a/i")
            page.click("xpath=//*[@id='breadcrumbs']/div[2]/div/ul/li[3]/ul/li/a")

            # Nhập tên file cần lưu
            print(f" -> Đang nhập tên file: {file_name_val}")
            page.click("id=fileName_ctrl")
            page.fill("id=fileName_ctrl", file_name_val)
            time.sleep(2)

            # Bấm nút Đồng ý tải xuống trong Modal và bắt sự kiện Download
            print(" -> Đang tải file Excel về...")
            with page.expect_download() as download_info:
                page.click("xpath=/html/body/div[1]/div/div/div/div[3]/button[1]")
            
            download = download_info.value
            save_path = os.path.join("./downloads", f"{file_name_val}.xlsx")
            download.save_as(save_path)
            print(f" -> TẢI THÀNH CÔNG: {save_path}")

            time.sleep(3)

        browser.close()
        print("\n=== HOÀN THÀNH TẤT CẢ CÁC KHO ===")

if __name__ == "__main__":
    run_automation()
