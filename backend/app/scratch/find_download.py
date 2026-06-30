import sys
import os

main_path = os.path.join(os.path.dirname(__file__), "..", "main.py")
output_path = os.path.join(os.path.dirname(__file__), "search_results.txt")

with open(main_path, "r", encoding="utf-8") as f:
    lines = f.readlines()

results = []
for i, line in enumerate(lines):
    if "download" in line.lower():
        # Strip non-ascii characters to avoid encoding crash when displaying
        clean_line = line.strip().encode("ascii", "ignore").decode("ascii")
        results.append(f"{i+1}: {clean_line}")

with open(output_path, "w", encoding="utf-8") as out:
    out.write("\n".join(results))

print(f"Done! Found {len(results)} matches. Results written to: {output_path}")
