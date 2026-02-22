import requests
import json
import sys

# Set stdout to utf-8
sys.stdout.reconfigure(encoding='utf-8')

try:
    r = requests.get("http://localhost:8000/api/characters/38")
    data = r.json()
    print(f"Name: {data['name']}")
    print(f"Description: {data['description']}")
    print(f"System Prompt (Snippet): {data['system_prompt'][:200]}...")
except Exception as e:
    print(e)
