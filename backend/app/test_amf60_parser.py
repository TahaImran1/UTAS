#!/usr/bin/env python3
import re
import json

# Simulated AMF60 body from your logs
test_body = b'\x7f\x00\x00\x00{"user_id":"500","user_name":"temp","user_privilege":"MANAGER","enroll_data_array":[{"backup_number":0,"enroll_data":"BIN_1"}]}d\x02\x00\x00p\x034\x1ddGPl\x00\x00@\x00\x02\x07\x12\x04\x0b\x08\x10\r\x03\x07\x06\x01\x05\t\x00\x0e\x11\x0f\x06\x13/>kfn[X~8557L\'o\x00\x00\x00'

print("Testing AMF60 JSON parser")
print("-" * 40)

# Method that works (non-greedy + clean)
match = re.search(rb'\{[^}]*\}', test_body, re.DOTALL)
if match:
    json_str = match.group(0).decode('utf-8', errors='ignore')
    # Keep only printable chars
    json_str = ''.join(c for c in json_str if ord(c) >= 32 or c in '\n\r\t')
    data = json.loads(json_str)
    print("✓ SUCCESS: Parsed data =", data)
else:
    print("✗ FAILED: No JSON found")