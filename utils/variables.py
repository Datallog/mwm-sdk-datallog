import os


datallog_api_url = os.getenv('DATALLOG_SDK_BACKEND_URL', "https://api-mwm.datallog.com").rstrip("/")
datallog_web_url = os.getenv('DATALLOG_SDK_WEB_URL', "https://mwm.datallog.com").rstrip("/")
datallog_url = datallog_api_url
