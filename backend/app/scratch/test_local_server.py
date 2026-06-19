import requests
import struct
import json

url = "http://127.0.0.1:4370/iclock/cdata"
headers = {
    "dev_id": "AMT602511730",
    "request_code": "realtime_enroll_data",
    "trans_id": "123",
    "blk_no": "456",
    "Content-Type": "application/octet-stream"
}

# The request body starts with a 4-byte length prefix (little endian), followed by JSON.
json_data = {"user_id":"500","user_name":"temp","user_privilege":"MANAGER","enroll_data_array":[{"backup_number":0,"enroll_data":"BIN_1"}]}
json_bytes = json.dumps(json_data).encode("utf-8")
req_body = struct.pack("<I", len(json_bytes)) + json_bytes + b"SOME_BINARY_FINGERPRINT_DATA"

print("Sending request to local server...")
try:
    r = requests.post(url, headers=headers, data=req_body, timeout=5)
    print("Response Status Code:", r.status_code)
    print("Response Headers:")
    for k, v in r.headers.items():
        print(f"  {k}: {v}")
    
    resp_body = r.content
    print("Response Body Length:", len(resp_body))
    if len(resp_body) >= 4:
        json_len = struct.unpack("<I", resp_body[:4])[0]
        print("Unpacked JSON length prefix:", json_len)
        try:
            parsed_json = json.loads(resp_body[4:4+json_len].decode("utf-8"))
            print("Parsed Response JSON:", parsed_json)
        except Exception as e:
            print("Failed to parse JSON body:", e)
            print("Raw Response body:", resp_body)
    else:
        print("Raw Response body:", resp_body)
except Exception as e:
    print("Error:", e)
