import base64
import requests
import getpass
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta

# ===== CONFIGURATION =====
BASE_URL = "https://api.five9.com/wsadmin/v13/AdminWebService"
REPORT_NAME = ""
FOLDER_NAME = ""  # Update if needed

# Set timezone offset for Five9 in format ±HH:MM
TZ_OFFSET = "-05:00"

# ===== GENERATE CRITERIA TIMES =====
now = datetime.now()
today_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
start_time = today_midnight - timedelta(days=1) + timedelta(minutes=1)  # 12:01 AM previous day
end_time = today_midnight  # Midnight current day

def format_five9(dt, offset):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000") + offset

start_str = format_five9(start_time, TZ_OFFSET)
end_str = format_five9(end_time, TZ_OFFSET)

print(f"Start Time: {start_str}")
print(f"End Time: {end_str}")

# ===== PROMPT FOR CREDENTIALS =====
username = input("Enter username: ")
password = getpass.getpass("Enter password: ")

# ===== BASIC AUTH HEADER =====
auth_string = f"{username}:{password}"
auth_base64 = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")

headers = {
    "SOAPAction": '""',  # Required for Five9 SOAP
    "Authorization": f"Basic {auth_base64}",
    "Content-Type": "text/xml; charset=utf-8"
}

# ===== 1. RUN REPORT =====
soap_body_run_report = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ser="http://service.admin.ws.five9.com/">'
    '<soapenv:Header/>'
    '<soapenv:Body>'
    '<ser:runReport>'
    f'<folderName>{FOLDER_NAME}</folderName>'
    f'<reportName>{REPORT_NAME}</reportName>'
    '<criteria>'
    '<time>'
    f'<end>{end_str}</end>'
    f'<start>{start_str}</start>'
    '</time>'
    '</criteria>'
    '</ser:runReport>'
    '</soapenv:Body>'
    '</soapenv:Envelope>'
)

print("Submitting runReport request...")
response = requests.post(BASE_URL, headers=headers, data=soap_body_run_report)

if response.status_code != 200:
    print("Error running report:")
    print(response.status_code)
    print(response.text)
    raise SystemExit("Exiting due to SOAP error.")

root = ET.fromstring(response.content)
identifier_elem = root.find('.//return')
identifier = identifier_elem.text if identifier_elem is not None else None

if not identifier:
    raise Exception("No report identifier returned from runReport call")

print(f"Report identifier: {identifier}")

# ===== 2. POLL UNTIL REPORT COMPLETES =====
is_running = True
while is_running:
    soap_body_is_running = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:ser="http://service.admin.ws.five9.com/">'
        '<soapenv:Header/>'
        '<soapenv:Body>'
        '<ser:isReportRunning>'
        f'<identifier>{identifier}</identifier>'
        '<timeout>30</timeout>'
        '</ser:isReportRunning>'
        '</soapenv:Body>'
        '</soapenv:Envelope>'
    )

    response = requests.post(BASE_URL, headers=headers, data=soap_body_is_running)
    if response.status_code != 200:
        print("Error polling report status:")
        print(response.status_code)
        print(response.text)
        raise SystemExit("Exiting due to SOAP error.")

    root = ET.fromstring(response.content)
    status_elem = root.find('.//return')
    status_text = status_elem.text if status_elem is not None else None

    if status_text == 'false':
        print("Report is complete.")
        is_running = False
    else:
        print("Report still running... waiting 5 seconds")
        time.sleep(5)

# ===== 3. GET REPORT RESULT CSV =====
soap_body_get_csv = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ser="http://service.admin.ws.five9.com/">'
    '<soapenv:Header/>'
    '<soapenv:Body>'
    '<ser:getReportResultCsv>'
    f'<identifier>{identifier}</identifier>'
    '</ser:getReportResultCsv>'
    '</soapenv:Body>'
    '</soapenv:Envelope>'
)

print("Fetching report CSV...")
response = requests.post(BASE_URL, headers=headers, data=soap_body_get_csv)
if response.status_code != 200:
    print("Error retrieving report CSV:")
    print(response.status_code)
    print(response.text)
    raise SystemExit("Exiting due to SOAP error.")

root = ET.fromstring(response.content)
csv_elem = root.find('.//return')

if csv_elem is not None and csv_elem.text:
    with open("report.csv", "w", encoding="utf-8") as f:
        f.write(csv_elem.text)
    print("Report CSV saved as report.csv")
else:
    print("No CSV data returned from report.")
