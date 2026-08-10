import os
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Thư viện đẩy file lên Google Drive
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Đọc cấu hình từ GitHub Secrets
ERP_USER = os.getenv("ERP_USERNAME")
ERP_PASS = os.getenv("ERP_PASSWORD")
GDRIVE_JSON = os.getenv("GDRIVE_CREDENTIALS_JSON")
FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")

WAREHOUSES = [
    {"code": "khoda", "prefix": "tkkd_da"},
    {"code": "khogt", "prefix": "tkkd_gt"},
    {"code": "khoak", "prefix": "tkkd_ak"},
    {"code": "khosg", "prefix": "tkkd_hcm"},
    {"code": "khovc", "prefix": "tkkd_vc"},
    {"code": "khojp", "prefix": "tkkd_jp"},
]

DOWNLOAD_DIR = os.path.abspath("./downloads")

def upload_files_to_gdrive(download_dir, folder_id):
    """Đẩy từng file Excel lên Google Drive"""
    if not GDRIVE_JSON or not folder_id:
        print("[!] Thieu GDRIVE_CREDENTIALS_JSON hoac GDRIVE_FOLDER_ID. Bo qua upload.")
        return

    print("\n[+] Bat dau upload file len Google Drive...")
    try:
        creds_dict = json.loads(GDRIVE_JSON)
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build('drive', 'v3', credentials=creds)

        for file_name in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file_name)
            if os.path.isfile(file_path):
                file_metadata = {
                    'name': file_name,
                    'parents': [folder_id]
                }
                media = MediaFileUpload(
                    file_path, 
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    resumable=True
                )
                uploaded_file = service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id'
                ).execute()
                print(f"[✓] Da upload thanh cong: {file_name} (ID: {uploaded_file.get('id')})")
    except Exception as e:
        print(f"[!] Loi khi upload Google Drive: {str(e)}")

def setup_driver(download_path):
    os.makedirs(download_path, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
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
        print("[+] Dang truy cap trang dang nhap ERP...")
        driver.get("http://103.149.99.95:8011/Account/Login")
        
        user_input = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
        pass_input = driver.find_element(By.ID, "pass_word")
        
        user_input.clear()
        user_input.send_keys(ERP_USER)
        pass_input.clear()
        pass_input.send_keys(ERP_PASS)
        
        try:
            login_btn = driver.find_element(By.XPATH, "//form//button")
            login_btn.click()
        except Exception:
            pass_input.send_keys(Keys.RETURN)
            
        time.sleep(3)
        print("[+] Dang nhap thanh cong!")

        current_time_str = datetime.now().strftime("%d.%m.%Y %H%M")

        for item in WAREHOUSES:
            code = item["code"]
            prefix = item["prefix"]
            file_name = f"{prefix} {current_time_str}"
            
            print(f"[+] Xu ly kho: {code} -> File: {file_name}")
            driver.get("http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung")
            time.sleep(3)

            tag_input = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/tags-input/div/div/input')
            ))
            tag_input.clear()
            tag_input.send_keys(code)
            tag_input.send_keys(Keys.ENTER)

            try:
                tag_icon = driver.find_element(By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/div/i')
                tag_icon.click()
            except Exception:
                pass
            time.sleep(2)

            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="search"]/span')))
            search_btn.click()
            time.sleep(4)

            btn_breadcrumb = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/a')))
            btn_breadcrumb.click()
            time.sleep(1)

            btn_export_icon = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/ul/li[3]/a/i')))
            btn_export_icon.click()
            time.sleep(1)

            btn_export_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Export Excel')))
            btn_export_link.click()
            time.sleep(2)

            file_name_input = wait.until(EC.presence_of_element_located((By.ID, "fileName_ctrl")))
            file_name_input.clear()
            file_name_input.send_keys(file_name)
            time.sleep(1)

            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[1]')))
            confirm_btn.click()
            
            print(f"[✓] Da tai xong file temp: {file_name}")
            time.sleep(10)

    except Exception as e:
        print(f"[!] Loi trong qua trinh truy cap ERP: {str(e)}")
    finally:
        driver.quit()

    upload_files_to_gdrive(DOWNLOAD_DIR, FOLDER_ID)

if __name__ == "__main__":
    run_download()
