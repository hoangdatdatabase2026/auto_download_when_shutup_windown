name: Run ERP Automation

on:
  workflow_dispatch: # Vẫn giữ lệnh này để bạn có thể bấm nút "Run workflow" chạy bằng tay bất cứ lúc nào
  schedule:
    # Cú pháp Cron chạy lúc: phút 00, các giờ 0, 2, 4, 6, 8, 10 (Giờ UTC)
    # Tương đương: 07:00, 09:00, 11:00, 13:00, 15:00, 17:00 (Giờ Việt Nam) mỗi ngày
    - cron: '0 0,2,4,6,8,10 * * *'

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout Repository
      uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'

    - name: Install Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install playwright google-api-python-client google-auth-httplib2 google-auth-oauthlib
        playwright install chromium

    - name: Chạy Script tự động tải báo cáo ERP
      env:
        # Truyền biến Secrets từ GitHub vào Python
        ERP_USERNAME: ${{ secrets.ERP_USERNAME }}
        ERP_PASSWORD: ${{ secrets.ERP_PASSWORD }}
        GDRIVE_FOLDER_ID: ${{ secrets.GDRIVE_FOLDER_ID }}
        GDRIVE_CREDENTIALS_JSON: ${{ secrets.GDRIVE_CREDENTIALS_JSON }}
      run: python main.py
