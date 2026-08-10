import os
import json
import time
import traceback
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Thư viện Google Drive API
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Đọc Secret từ GitHub
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
    print("\n" + "="*60)
    print("[GIAI DOAN 4] BAT DAU UPLOAD FILE LEN GOOGLE DRIVE")
    print("="*60)
    
    if not GDRIVE_JSON or not folder_id:
        print("[!] LOI: Thieu GDRIVE_CREDENTIALS_JSON hoac GDRIVE_FOLDER_ID trong Secret!")
        return

    try:
        creds_dict = json.loads(GDRIVE_JSON)
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build('drive', 'v3', credentials=creds)

        files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
        total_files = len(files)
        print(f"[*] Tim thay {total_files} file trong thu muc cho upload...")

        for idx, file_name in enumerate(files, 1):
            file_path = os.path.join(download_dir, file_name)
            print(f" -> [{idx}/{total_files}] Dang upload file: {file_name}...")
            
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
            print(f"    [✓] Upload thanh cong! ID File Drive: {uploaded_file.get('id')}")
            
        print("\n[✓] HOAN THANH UPLOAD TOAN BO FILE LEN GOOGLE DRIVE!")

    except Exception as e:
        print(f"[!] LOI KHI UPLOAD GOOGLE DRIVE:")
        traceback.print_exc()

def setup_driver(download_path):
    print("\n[GIAI DOAN 1] KHOI TAO TRINH DUYET CHROME...")
    os.makedirs(download_path, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    # Gia lap User-Agent trinh duyat that de tranh bi web block che do Headless
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    prefs = {
        "download.default_directory": download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    print("[✓] Khoi tao Trinh duyet thanh cong!")
    return driver

def run_download():
    print("="*60)
    print("BAT DAU QUI TRINH TU DONG HOA DOWNLOAD ERP")
    print("="*60)
    
    driver = setup_driver(DOWNLOAD_DIR)
    wait = WebDriverWait(driver, 25) # Tang time wait len 25s cho cac trang load cham
    
    # --- GIAI DOAN 2: DANG NHAP ---
    try:
        print("\n[GIAI DOAN 2] DANG NHAP HE THONG ERP...")
        print(" -> Step 2.1: Truy cap trang Login...")
        driver.get("http://103.149.99.95:8011/Account/Login")
        
        print(" -> Step 2.2: Cho va nhap Username/Password...")
        user_input = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
        pass_input = driver.find_element(By.ID, "pass_word")
        
        user_input.clear()
        user_input.send_keys(ERP_USER)
        pass_input.clear()
        pass_input.send_keys(ERP_PASS)
        
        print(" -> Step 2.3: Nhan nut Dang nhap...")
        try:
            login_btn = driver.find_element(By.XPATH, "//form//button")
            login_btn.click()
        except Exception:
            pass_input.send_keys(Keys.RETURN)
            
        time.sleep(5) # Cho he thong luu Cookie va phien dang nhap
        print("[✓] Dang nhap thanh cong!")

    except Exception as e:
        print("[!] LOI NGHITEM TRONG QUA TRINH DANG NHAP ERP:")
        traceback.print_exc()
        driver.quit()
        return

    # --- GIAI DOAN 3: LAP QUA CAC KHO ---
    current_time_str = datetime.now().strftime("%d.%m.%Y %H%M")
    total_warehouses = len(WAREHOUSES)

    print(f"\n[GIAI DOAN 3] TAI BAO CAO CHO {total_warehouses} KHO...")

    for idx, item in enumerate(WAREHOUSES, 1):
        code = item["code"]
        prefix = item["prefix"]
        file_name = f"{prefix} {current_time_str}"
        
        print(f"\n--------------------------------------------------")
        print(f"[*] [KHO {idx}/{total_warehouses}] DANG XU LY: {code.upper()} -> File: {file_name}")
        print(f"--------------------------------------------------")
        
        try:
            print(f" -> Step 3.1: Mo URL bao cao ton kho...")
            driver.get("http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung")
            time.sleep(4) # Cho Angular framework render giao dien

            print(f" -> Step 3.2: Tim va nhap ma kho [{code}]...")
            tag_input = wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/tags-input/div/div/input')
            ))
            tag_input.clear()
            tag_input.send_keys(code)
            tag_input.send_keys(Keys.ENTER)
            time.sleep(1)

            try:
                tag_icon = driver.find_element(By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/div/i')
                tag_icon.click()
            except Exception:
                pass
            time.sleep(2)

            print(f" -> Step 3.3: Nhan nut Tim kiem...")
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="search"]/span')))
            search_btn.click()
            time.sleep(5) # Cho du lieu bang tra ve

            print(f" -> Step 3.4: Mo menu Breadcrumb Export...")
            btn_breadcrumb = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/a')))
            btn_breadcrumb.click()
            time.sleep(1.5)

            print(f" -> Step 3.5: Nhan Icon Export...")
            btn_export_icon = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/ul/li[3]/a/i')))
            btn_export_icon.click()
            time.sleep(1.5)

            print(f" -> Step 3.6: Chon link Export Excel...")
            btn_export_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Export Excel')))
            btn_export_link.click()
            time.sleep(2)

            print(f" -> Step 3.7: Nhap ten file [{file_name}] va Xac nhan...")
            file_name_input = wait.until(EC.presence_of_element_located((By.ID, "fileName_ctrl")))
            file_name_input.clear()
            file_name_input.send_keys(file_name)
            time.sleep(1)

            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[1]')))
            confirm_btn.click()
            
            print(f" [✓] Hoan tat kho [{code.upper()}]. Cho file tai ve...")
            time.sleep(10)

        except Exception as e:
            print(f" [!] LOI KHI TAI KHO [{code.upper()}]:")
            traceback.print_exc()
            print(" [->] Bo qua kho nay va tiep tuc kho ke tiep...")

    print("\n[✓] DA DUYET XONG TOAN BO DANH SACH KHO!")
    driver.quit()

    # Thực thi Upload Drive
    upload_files_to_gdrive(DOWNLOAD_DIR, FOLDER_ID)

if __name__ == "__main__":
    run_download()
