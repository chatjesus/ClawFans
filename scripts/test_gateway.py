import requests, sys
sys.stdout.reconfigure(encoding='utf-8')

# Check sessions
r = requests.get('http://localhost:8000/api/gateway/sessions')
for s in r.json():
    print(f"  Session {s['id']}: {s['character_name']} on {s['platform']} ({s['platform_user_id']})")

# Check message history for session 1
r = requests.get('http://localhost:8000/api/gateway/sessions/1/messages')
print(f"\nSession 1 messages: {len(r.json())} messages")
for m in r.json()[-3:]:
    print(f"  [{m['role']}] {m['content'][:80]}...")

# Gateway API endpoints
r = requests.get('http://localhost:8000/openapi.json')
paths = [p for p in r.json()['paths'] if 'gateway' in p]
print(f"\nGateway endpoints: {paths}")
