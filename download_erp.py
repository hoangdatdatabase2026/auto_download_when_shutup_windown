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

def print_status(step, message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{step}] {message}", flush=True)

def list_downloaded_files():
    """Kiểm tra và liệt kê các file Excel đã tải về thành công"""
    if not os.path.exists(DOWNLOAD_DIR):
        return []
    return [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)) and not f.endswith('.crdownload')]

def upload_files_to_gdrive(download_dir, folder_id):
    """Đẩy từng file Excel lên Google Drive"""
    print("\n" + "="*70, flush=True)
    print_status("BUOC 4/4", "BAT DAU UPLOAD FILE LEN GOOGLE DRIVE")
    print("="*70, flush=True)
    
    if not GDRIVE_JSON or not folder_id:
        print_status("LOI DRIVE", "Thieu GDRIVE_CREDENTIALS_JSON hoac GDRIVE_FOLDER_ID!")
        return

    try:
        creds_dict = json.loads(GDRIVE_JSON)
        scopes = ['https://www.googleapis.com/auth/drive']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        service = build('drive', 'v3', credentials=creds)

        files = list_downloaded_files()
        total_files = len(files)
        print_status("DRIVE INFO", f"Phat hien {total_files} file Excel trong thu muc chờ upload.")

        if total_files == 0:
            print_status("CANH BAO", "Khong co file nao trong thu muc de upload!")
            return

        for idx, file_name in enumerate(files, 1):
            file_path = os.path.join(download_dir, file_name)
            file_size_kb = round(os.path.getsize(file_path) / 1024, 2)
            print_status("UPLOADING", f"[{idx}/{total_files}] Dang upload: {file_name} ({file_size_kb} KB)...")
            
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
            print_status("UPLOAD SUCCESS", f"Thanh cong! File ID Drive: {uploaded_file.get('id')}")
            
        print_status("BUOC 4/4", "HOAN THANH TOAN BO TIEN TRINH UPLOAD!")

    except Exception as e:
        print_status("LOI UPLOAD", f"Loi khi ket noi Google Drive API: {str(e)}")
        traceback.print_exc()

def setup_driver(download_path):
    print_status("BUOC 1/4", "KHOI TAO TRINH DUYET CHROME HEADLESS...")
    os.makedirs(download_path, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    prefs = {
        "download.default_directory": download_path,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    print_status("BUOC 1/4", "Khoi tao Chrome thanh cong.")
    return driver

def run_download():
    print("="*70, flush=True)
    print_status("START", "BAT DAU TIEN TRINH TU DONG HOA CHAY NGAM")
    print("="*70, flush=True)
    
    driver = setup_driver(DOWNLOAD_DIR)
    wait = WebDriverWait(driver, 30)
    
    # --- BƯỚC 2: DĂNG NHẬP ---
    try:
        print("\n" + "-"*50, flush=True)
        print_status("BUOC 2/4", "DANG NHAP HE THONG ERP")
        print_status("2.1", "Truy cap URL Đang nhap: http://103.149.99.95:8011/Account/Login")
        driver.get("http://103.149.99.95:8011/Account/Login")
        time.sleep(2)
        print_status("2.1 STATUS", f"Trang hien tai: Title='{driver.title}', URL='{driver.current_url}'")

        print_status("2.2", f"Tim o nhap Username/Password va dien tai khoan [{ERP_USER}]...")
        user_input = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
        pass_input = driver.find_element(By.ID, "pass_word")
        
        user_input.clear()
        user_input.send_keys(ERP_USER)
        pass_input.clear()
        pass_input.send_keys(ERP_PASS)
        
        print_status("2.3", "Nhan nut 'Dang nhap'...")
        try:
            login_btn = driver.find_element(By.XPATH, "//form//button")
            login_btn.click()
        except Exception:
            pass_input.send_keys(Keys.RETURN)
            
        time.sleep(5)
        
        # VERIFY LOGIN SUCCESS
        current_url = driver.current_url
        print_status("2.4 CHECK LOGIN", f"URL sau khi dang nhap: {current_url}")
        if "Login" not in current_url:
            print_status("2.4 CHECK LOGIN", "-> XAC NHAN: DANG NHAP THANH CONG!")
        else:
            print_status("2.4 CHECK LOGIN", "-> CANH BAO: Vẫn đang đứng ở trang Login. Kiểm tra lại Username/Password!")

    except Exception as e:
        print_status("LOI BUOC 2", f"Khong the dang nhap: {str(e)}")
        traceback.print_exc()
        driver.quit()
        return

    # --- BƯỚC 3: DUYỆT QUA TỪNG KHO ---
    current_time_str = datetime.now().strftime("%d.%m.%Y %H%M")
    total_warehouses = len(WAREHOUSES)

    print("\n" + "="*70, flush=True)
    print_status("BUOC 3/4", f"BAT DAU XU LY TAI BAO CAO CHO {total_warehouses} KHO")
    print("="*70, flush=True)

    for idx, item in enumerate(WAREHOUSES, 1):
        code = item["code"]
        prefix = item["prefix"]
        file_name = f"{prefix} {current_time_str}"
        
        print(f"\n>>> [KHO {idx}/{total_warehouses}] KHO: {code.upper()} | TEN FILE DU KIEN: {file_name}", flush=True)
        
        try:
            print_status(f"3.{idx}.1", "Mở trực tiếp URL Báo cáo Tồn khả dụng...")
            driver.get("http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung")
            time.sleep(5) # Cho Angular framework render DOM
            
            print_status(f"3.{idx}.1 STATUS", f"URL hien tai: {driver.current_url}")
            
            # Neu bi day ve lai Login do phien bi ngat
            if "Login" in driver.current_url:
                print_status(f"3.{idx}.1 WARN", "Bi day ve trang Login! Tien hanh dang nhap lai...")
                u = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
                p = driver.find_element(By.ID, "pass_word")
                u.clear(); u.send_keys(ERP_USER)
                p.clear(); p.send_keys(ERP_PASS)
                p.send_keys(Keys.RETURN)
                time.sleep(5)
                driver.get("http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung")
                time.sleep(5)

            print_status(f"3.{idx}.2", f"Tim o 'ma_kho' va nhap ma [{code}]...")
            
            # Sử dụng XPath linh hoạt hơn cho ô input tags
            tag_input = None
            try:
                tag_input = wait.until(EC.presence_of_element_located((By.XPATH, '//*[@id="ma_kho"]//input')))
            except Exception:
                tag_input = wait.until(EC.presence_of_element_located((By.XPATH, '//div[@id="ma_kho"]//tags-input//input')))

            tag_input.clear()
            tag_input.send_keys(code)
            tag_input.send_keys(Keys.ENTER)
            time.sleep(1)
            print_status(f"3.{idx}.2 SUCCESS", f"-> Da dien '{code}' vao o ma_kho thanh cong!")

            try:
                tag_icon = driver.find_element(By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/div/i')
                tag_icon.click()
            except Exception:
                pass
            time.sleep(2)

            print_status(f"3.{idx}.3", "Nhan nut 'Tim kiem'...")
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="search"]/span')))
            search_btn.click()
            time.sleep(5)
            print_status(f"3.{idx}.3 SUCCESS", "-> Da bam nut Tim kiem. Bang du lieu da load.")

            print_status(f"3.{idx}.4", "Mo Breadcrumb & Menu Export Excel...")
            btn_breadcrumb = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/a')))
            btn_breadcrumb.click()
            time.sleep(1.5)

            btn_export_icon = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/ul/li[3]/a/i')))
            btn_export_icon.click()
            time.sleep(1.5)

            btn_export_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Export Excel')))
            btn_export_link.click()
            time.sleep(2)
            print_status(f"3.{idx}.4 SUCCESS", "-> Da mo Popup Export Excel.")

            print_status(f"3.{idx}.5", f"Dien ten file moi: [{file_name}] va bam 'Xac nhan'...")
            file_name_input = wait.until(EC.presence_of_element_located((By.ID, "fileName_ctrl")))
            file_name_input.clear()
            file_name_input.send_keys(file_name)
            time.sleep(1)

            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[1]')))
            confirm_btn.click()
            print_status(f"3.{idx}.5 SUCCESS", f"-> Da gui lenh tai file [{file_name}]. Dang cho 12 giay...")
            
            time.sleep(12)

            # Kiếm tra file vừa tải trong đĩa local
            current_files = list_downloaded_files()
            print_status(f"3.{idx}.6 CHECK FILE", f"Tong so file hien co trong thu muc local: {len(current_files)}")
            for f in current_files:
                if prefix in f:
                    size_kb = round(os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) / 1024, 2)
                    print_status(f"3.{idx}.6 CHECK FILE", f"-> XAC NHAN TAI THANH CONG: File '{f}' ({size_kb} KB)")

        except Exception as e:
            print_status(f"LOI KHO {code.upper()}", f"Khong the tai kho {code}: {str(e)}")
            print_status("PAGE DIAGNOSTIC", f"URL hien tai khi loi: {driver.current_url}")
            traceback.print_exc()
            print_status("SKIP", f"Bo qua kho [{code}] va tiep tuc kho ke tiep...")

    print_status("BUOC 3/4", "DA HOAN THANH TIEN TRINH DUYET CAC KHO!")
    driver.quit()

    # Thưc hiện Upload lên Google Drive
    upload_files_to_gdrive(DOWNLOAD_DIR, FOLDER_ID)

if __name__ == "__main__":
    run_download()
