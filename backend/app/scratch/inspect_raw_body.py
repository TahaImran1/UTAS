import re

log_path = r"e:\Projects\ZK\SUFI_LAST\sourse_code_ZKTECO\backend\app\scratch\amf60_raw_requests.log"

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Let's find "Body (Hex):" for realtime_enroll_data requests
matches = re.finditer(r'request_code:\s*realtime_enroll_data.*?Body \(Hex\):\s*([0-9a-fA-F\s\r\n]+?)(?:Body \(Decoded|\Z)', content, re.DOTALL)

for i, match in enumerate(matches):
    raw_hex = match.group(1)
    hex_str = re.sub(r'[^0-9a-fA-F]', '', raw_hex)
    
    try:
        body_bytes = bytes.fromhex(hex_str)
    except Exception as e:
        print(f"Error parsing hex for Match {i}: {e}")
        print(f"Raw hex length before filtering: {len(raw_hex)}")
        print(f"Raw hex preview: {raw_hex[:100]!r}")
        continue
        
    print(f"Match {i}: total length = {len(body_bytes)}")
    if len(body_bytes) >= 4:
        json_len = int.from_bytes(body_bytes[:4], byteorder='little')
        print(f"  JSON length: {json_len}")
        json_data = body_bytes[4:4+json_len]
        print(f"  JSON string: {json_data.decode('utf-8', errors='ignore')}")
        
        remaining = body_bytes[4+json_len:]
        print(f"  Remaining length: {len(remaining)}")
        if len(remaining) >= 4:
            bin_len = int.from_bytes(remaining[:4], byteorder='little')
            print(f"  Binary length prefix: {bin_len}")
            bin_data = remaining[4:4+bin_len]
            print(f"  Actual binary data length: {len(bin_data)}")
            
            # Is there more data after this binary block?
            post_bin = remaining[4+bin_len:]
            print(f"  Post-binary length: {len(post_bin)}")
            if len(post_bin) > 0:
                print(f"  Post-binary hex preview: {post_bin[:20].hex()}")
                # Let's see if there is a third block:
                if len(post_bin) >= 4:
                    third_len = int.from_bytes(post_bin[:4], byteorder='little')
                    print(f"  Third block length prefix: {third_len}")
                    third_data = post_bin[4:4+third_len]
                    print(f"  Third block actual length: {len(third_data)}")
                    post_third = post_bin[4+third_len:]
                    print(f"  Post-third length: {len(post_third)}")
                    if len(post_third) > 0:
                        print(f"  Post-third hex preview: {post_third[:20].hex()}")
                        
    print("-" * 60)
    if i >= 2:
        break
