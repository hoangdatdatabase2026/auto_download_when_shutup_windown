import os
import sys
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

REPORT_URL = "http://103.149.99.95:8011/Solution/ERP/#/SO/Report/SOBCTonKhaDung"

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
    if not os.path.exists(DOWNLOAD_DIR):
        return []
    return [f for f in os.listdir(DOWNLOAD_DIR) if os.path.isfile(os.path.join(DOWNLOAD_DIR, f)) and not f.endswith('.crdownload')]

def upload_files_to_gdrive(download_dir, folder_id):
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
        print_status("DRIVE INFO", f"Phat hien {total_files} file Excel trong thu muc cho upload.")

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
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
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

def type_with_js_events(driver, element, value):
    element.clear()
    element.send_keys(value)
    driver.execute_script("""
        var elem = arguments[0];
        elem.dispatchEvent(new Event('input', { bubbles: true }));
        elem.dispatchEvent(new Event('change', { bubbles: true }));
        elem.dispatchEvent(new Event('blur', { bubbles: true }));
    """, element)

def handle_modal_popup(driver):
    time.sleep(2)
    confirm_words = ["CO", "CÓ", "Có", "có", "Xác nhận", "OK", "Yes"]
    for word in confirm_words:
        try:
            buttons = driver.find_elements(By.XPATH, f"//button[contains(text(), '{word}')] | //span[contains(text(), '{word}')] | //a[contains(text(), '{word}')]")
            for btn in buttons:
                if btn.is_displayed():
                    print_status("MODAL POPUP", f"-> Phat hien Popup xac nhan! Dang bam nut '{word}'...")
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(2)
                    return True
        except Exception:
            pass
    return False

def perform_login_with_retry(driver, wait, max_retries=3):
    print("\n" + "-"*50, flush=True)
    print_status("BUOC 2/4", "TIEN HANH DANG NHAP HE THONG ERP")

    for attempt in range(1, max_retries + 1):
        print_status(f"LAN DANG NHAP {attempt}/{max_retries}", "Dang mo trang Login: http://103.149.99.95:8011/Account/Login")
        
        try:
            driver.get("http://103.149.99.95:8011/Account/Login")
            time.sleep(3)

            user_input = wait.until(EC.presence_of_element_located((By.ID, "user_name")))
            pass_input = driver.find_element(By.ID, "pass_word")

            type_with_js_events(driver, user_input, ERP_USER if ERP_USER else "")
            type_with_js_events(driver, pass_input, ERP_PASS if ERP_PASS else "")
            time.sleep(1)

            print_status(f"LAN DANG NHAP {attempt}/{max_retries}", "Gui lenh Dang nhap...")
            
            login_clicked = False
            try:
                login_btn = driver.find_element(By.XPATH, "//form//button | //button[@type='submit'] | //button[contains(text(),'Đăng nhập')]")
                driver.execute_script("arguments[0].click();", login_btn)
                login_clicked = True
            except Exception:
                pass

            if not login_clicked:
                pass_input.send_keys(Keys.RETURN)

            handle_modal_popup(driver)

            print_status(f"LAN DANG NHAP {attempt}/{max_retries}", "Kiem tra dieu huong trang...")
            
            start_time = time.time()
            while time.time() - start_time < 18:
                curr_url = driver.current_url
                if "OverviewDisplay" in curr_url or "Solution/ERP/#" in curr_url:
                    print_status("DANG NHAP THANH CONG", f"-> DA DEN DUNG PAGE TARGET: {curr_url}")
                    return True
                handle_modal_popup(driver)
                time.sleep(2)

            curr_url = driver.current_url
            print_status("THAT BAI", f"Lan {attempt} dung tai URL: {curr_url}")

        except Exception as e:
            print_status("LOI THAO TAC", f"Loi lan {attempt}: {str(e)}")

        time.sleep(3)

    return False

def run_download():
    print("="*70, flush=True)
    print_status("START", "BAT DAU TIEN TRINH TU DONG HOA CHAY NGAM")
    print("="*70, flush=True)
    
    driver = setup_driver(DOWNLOAD_DIR)
    wait = WebDriverWait(driver, 30)
    
    login_success = perform_login_with_retry(driver, wait, max_retries=3)

    if not login_success:
        print("\n" + "!"*70, flush=True)
        print_status("FATAL ERROR", "DANG NHAP THAT BAI SAU 3 LAN THU LAI!")
        print_status("FATAL ERROR", "STOP CODE: DUNG TIEN TRINH CHU DONG.")
        print("!"*70 + "\n", flush=True)
        driver.quit()
        sys.exit(1)

    current_time_str = datetime.now().strftime("%d.%m.%Y %H%M")
    total_warehouses = len(WAREHOUSES)

    print("\n" + "="*70, flush=True)
    print_status("BUOC 3/4", f"BAT DAU XU LY TAI BAO CAO CHO {total_warehouses} KHO")
    print("="*70, flush=True)

    # ĐIỀU HƯỚNG SANG TRANG BÁO CÁO TỒN KHẢ DỤNG QUA ANGULAR ROUTER
    print_status("3.0 ROUTING", f"Chuyen huong Angular Route sang trang Bieu mau: {REPORT_URL}")
    driver.get(REPORT_URL)
    driver.execute_script("window.location.hash = '#/SO/Report/SOBCTonKhaDung';")
    time.sleep(5)

    for idx, item in enumerate(WAREHOUSES, 1):
        code = item["code"]
        prefix = item["prefix"]
        file_name = f"{prefix} {current_time_str}"
        
        print(f"\n>>> [KHO {idx}/{total_warehouses}] KHO: {code.upper()} | TEN FILE DU KIEN: {file_name}", flush=True)
        
        try:
            # Đảm bảo trang đã load đúng vị trí Báo cáo Tồn kho
            if "#/SO/Report/SOBCTonKhaDung" not in driver.current_url:
                print_status(f"3.{idx}.1", "Mo URL Bao cao Ton kha dung...")
                driver.get(REPORT_URL)
                driver.execute_script("window.location.hash = '#/SO/Report/SOBCTonKhaDung';")
                time.sleep(4)
            
            print_status(f"3.{idx}.1 STATUS", f"URL hien tai: {driver.current_url}")

            # ĐIỀN MÃ KHO THEO XPATH CHÍNH XÁC DO BẠN CUNG CẤP
            print_status(f"3.{idx}.2", f"Tim o 'ma_kho' va nhap ma [{code}]...")
            ma_kho_xpath = '//*[@id="ma_kho"]/itg-tags-input/div/div/tags-input/div/div/input'
            
            tag_input = wait.until(EC.presence_of_element_located((By.XPATH, ma_kho_xpath)))
            
            # Click trực tiếp để activate ô tags-input
            driver.execute_script("arguments[0].click();", tag_input)
            time.sleep(0.5)
            
            type_with_js_events(driver, tag_input, code)
            tag_input.send_keys(Keys.ENTER)
            time.sleep(1)
            print_status(f"3.{idx}.2 SUCCESS", f"-> Da dien '{code}' vao o ma_kho!")

            # Click Icon tag nếu có
            try:
                tag_icon = driver.find_element(By.XPATH, '//*[@id="ma_kho"]/itg-tags-input/div/div/div/i')
                driver.execute_script("arguments[0].click();", tag_icon)
            except Exception:
                pass
            time.sleep(2)

            # BẤM NÚT "Xem báo cáo" / Search
            print_status(f"3.{idx}.3", "Nhan nut 'Xem bao cao' / Search...")
            search_btn = None
            try:
                search_btn = driver.find_element(By.XPATH, '//*[@id="search"]/span | //button[contains(text(),"Xem báo cáo")]')
            except Exception:
                search_btn = driver.find_element(By.XPATH, '//button[contains(@class,"btn-primary")]')
                
            driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(5)
            print_status(f"3.{idx}.3 SUCCESS", "-> Da bam nut Tim kiem/Xem bao cao.")

            # MỞ MENU EXPORT EXCEL
            print_status(f"3.{idx}.4", "Mo Breadcrumb & Menu Export Excel...")
            btn_breadcrumb = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/a')))
            driver.execute_script("arguments[0].click();", btn_breadcrumb)
            time.sleep(1.5)

            btn_export_icon = wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="breadcrumbs"]/div[2]/div/ul/li[3]/a/i')))
            driver.execute_script("arguments[0].click();", btn_export_icon)
            time.sleep(1.5)

            btn_export_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, 'Export Excel')))
            driver.execute_script("arguments[0].click();", btn_export_link)
            time.sleep(2)

            # ĐIỀN TÊN FILE TRONG MODAL POPUP
            print_status(f"3.{idx}.5", f"Dien ten file moi: [{file_name}] va Xac nhan...")
            file_name_input = wait.until(EC.presence_of_element_located((By.ID, "fileName_ctrl")))
            type_with_js_events(driver, file_name_input, file_name)
            time.sleep(1)

            confirm_btn = wait.until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[1]/div/div/div/div[3]/button[1]')))
            driver.execute_script("arguments[0].click();", confirm_btn)
            print_status(f"3.{idx}.5 SUCCESS", f"-> Da gui lenh tai file [{file_name}]. Cho 12 giay...")
            
            time.sleep(12)

            # KIỂM TRA FILE ĐÃ TẢI VỀ CHƯA
            current_files = list_downloaded_files()
            print_status(f"3.{idx}.6 CHECK FILE", f"Tong so file trong thu muc local: {len(current_files)}")
            for f in current_files:
                if prefix in f:
                    size_kb = round(os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) / 1024, 2)
                    print_status(f"3.{idx}.6 CHECK FILE", f"-> TAI THANH CONG: '{f}' ({size_kb} KB)")

        except Exception as e:
            print_status(f"LOI KHO {code.upper()}", f"Khong the tai kho {code}: {str(e)}")
            traceback.print_exc()

    print_status("BUOC 3/4", "HOAN THANH TIEN TRINH DUYET CAC KHO!")
    driver.quit()

    upload_files_to_gdrive(DOWNLOAD_DIR, FOLDER_ID)

if __name__ == "__main__":
    run_download()
