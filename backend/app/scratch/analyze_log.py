import re
from collections import Counter

log_path = r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app\scratch\amf60_raw_requests.log"

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Let's find all "request_code" headers or lines
req_codes = re.findall(r'request_code:\s*(\w+)', content)
print("Request codes found:")
print(Counter(req_codes))

# Also search for any "realtime_glog" or other request codes
for code in ["realtime_glog", "realtime_enroll_data", "receive_cmd"]:
    count = content.count(code)
    print(f"{code}: {count}")
