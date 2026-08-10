import os
import json
from playwright.sync_api import sync_playwright
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# 1. Đọc dữ liệu từ biến môi trường (Secrets)
ERP_URL = os.environ.get("ERP_URL")
ERP_USERNAME = os.environ.get("ERP_USERNAME")
ERP_PASSWORD = os.environ.get("ERP_PASSWORD")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID")
GDRIVE_JSON_STR = os.environ.get("GDRIVE_CREDENTIALS_JSON")

def download_erp_data():
    with sync_playwright() as p:
        # Bật trình duyệt Chromium ở chế độ ẩn (headless)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("1. Đang mở trang web ERP...")
        page.goto(ERP_URL)

        # -------------------------------------------------------------
        # ⚠️ LƯU Ý: Đổi 'input[name="username"]' thành Selector thực tế trang ERP của bạn
        # -------------------------------------------------------------
        print("2. Đang đăng nhập...")
        page.fill("input[name='username']", ERP_USERNAME)
        page.fill("input[name='password']", ERP_PASSWORD)
        page.click("button[type='submit']")

        # Chờ trang tải xong sau đăng nhập
        page.wait_for_load_state("networkidle")

        # -------------------------------------------------------------
        # ⚠️ LƯU Ý: Bắt sự kiện tải file khi bấm nút Xuất dữ liệu (Export)
        # Đổi 'button#export-btn' thành Selector thực tế nút Export của bạn
        # -------------------------------------------------------------
        print("3. Đang bấm nút xuất dữ liệu...")
        with page.expect_download() as download_info:
            page.click("button#export-btn")

        download = download_info.value
        download_path = f"./{download.suggested_filename}"
        download.save_as(download_path)

        browser.close()
        print(f"-> Đã tải file về máy chủ GitHub: {download_path}")
        return download_path

def upload_to_gdrive(file_path):
    print("4. Đang đẩy file lên Google Drive...")
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
    media = MediaFileUpload(file_path, resumable=True)

    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id"
    ).execute()

    print(f"-> THÀNH CÔNG! File ID trên Google Drive: {uploaded_file.get('id')}")

if __name__ == "__main__":
    file_downloaded = download_erp_data()
    upload_to_gdrive(file_downloaded)
