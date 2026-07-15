import json
import sys
from urllib.parse import urlparse
from collections import Counter

if len(sys.argv) < 2:
    print("Usage: python3 scripts/stat.py <path_to_jsonl>")
    sys.exit(1)

path = sys.argv[1]

doc_count = 0
total_chars = 0
total_words = 0
domains = Counter()

with open(path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        text = obj.get("text", "")
        url = obj.get("url", "")

        doc_count += 1
        total_chars += len(text)
        total_words += len(text.split())

        if url:
            domains[urlparse(url).netloc] += 1

print("Documents:", doc_count)
print("Avg chars/doc:", total_chars / doc_count if doc_count else 0)
print("Avg words/doc:", total_words / doc_count if doc_count else 0)
print("Unique domains:", len(domains))
print("Top 20 domains:", domains.most_common(20))