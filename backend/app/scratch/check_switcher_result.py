import re

log_path = r"C:\Users\ALIENWARE\.gemini\antigravity-ide\brain\5e59c274-146f-43e0-97e0-7963848ac12d\.system_generated\tasks\task-1665.log"

with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

print(f"Total log length: {len(content)} chars")

# Search for realtime_glog
glog_matches = [line for line in content.splitlines() if "realtime_glog" in line]
if glog_matches:
    print(f"Found {len(glog_matches)} realtime_glog log lines:")
    for m in glog_matches[:20]:
        print("  ", m)
else:
    print("realtime_glog NOT found in task-1665.log")

# Print the last 20 lines of the log
print("\nLast 20 lines of log:")
lines = content.splitlines()
for line in lines[-20:]:
    print(line)
