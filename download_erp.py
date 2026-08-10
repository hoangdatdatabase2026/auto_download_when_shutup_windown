pip install selenium webdriver-manager pydrive2

import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Danh sách cấu hình các kho
WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

# Thư mục lưu mặc định (có thể đè qua biến môi trường khi chạy trên Github)
DOWNLOAD_DIR = os.getenv("DOWNLOAD_PATH", r"G:\My Drive\Database\ton_kho")

def setup_driver(download_path):
    os.makedirs(download_path, exist_ok=True)
    options = webdriver.ChromeOptions()
    
    # Chạy ngầm không mở giao diện trình duyệt
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    # Đấu nối thư mục tải xuống mặc định
    prefs = {
        "download.default_directory": download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def run_download():
    driver = setup_driver(DOWNLOAD_DIR)
    wait = WebDriverWait(driver, 20)
    
    try:
        # 1. Đăng nhập hệ thống ERP
        print("[+] Đang truy cập trang đăng nhập ERP...")
        driver.get("http://103.149.99.95:8011/Account/Login")
        
        user_input = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
        pass_input = driver.find_element(By.ID, "pass_word")
        
        user_input.clear()
        user_input.send_keys("HD01566")
        pass_input.clear()
        pass_input.send_keys("8UIa8&!v")
        
        try:
            login_btn = driver.find_element(By.XPATH, "//form//button")
            login_btn.click()
        except Exception:
            pass_input.send_keys(Keys.RETURN)
            
        time.sleep(3)
        print("[+] Đăng nhập thành công!")

        # Format ngày giờ: dd.mm.yyyy HHMM
        current_time_str = datetime.now().strftime("%d.%m.%Y %H%M")

        # 2. Vòng lặp tải báo cáo theo từng kho
        for item in WAREHOUSES:
            code = item["code"]
            prefix = item["prefix"]
            file_name = f"{prefix} {current_time_str}"
            
            print(f"\n[+] Đang xử lý kho: {code} -> Tên file: {file_name}")
            driver.get("http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung")
            time.sleep(3)

            # Nhập mã kho vào ô tags-input
            tag_input = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/tags-input/div/div/input')
            ))
            tag_input.clear()
            tag_input.send_keys(code)
            tag_input.send_keys(Keys.ENTER)

            # Click icon nhận diện tag kho nếu cần
            try:
                tag_icon = driver.find_element(By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/div/i')
                tag_icon.click()
            except Exception:
                pass
            time.sleep(2)

            # Bấm Tìm kiếm
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="search"]/span')))
            search_btn.click()
            time.sleep(4)

            # Mở menu Export Excel
            btn_breadcrumb = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/a')))
            btn_breadcrumb.click()
            time.sleep(1)

            btn_export_icon = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/ul/li[3]/a/i')))
            btn_export_icon.click()
            time.sleep(1)

            btn_export_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Export Excel')))
            btn_export_link.click()
            time.sleep(2)

            # Điền tên file cần lưu trong Modal Popup
            file_name_input = wait.until(EC.presence_of_element_located((By.ID, "fileName_ctrl")))
            file_name_input.clear()
            file_name_input.send_keys(file_name)
            time.sleep(1)

            # Bấm nút xác nhận tải xuống
            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[1]')))
            confirm_btn.click()
            
            print(f"[✓] Đã gửi lệnh tải: {file_name}")
            time.sleep(10) # Chờ hoàn tất quá trình tải file

    except Exception as e:
        print(f"[!] Có lỗi xảy ra: {str(e)}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_download()
