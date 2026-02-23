import subprocess
import json
import urllib.request

# Check RAM
result = subprocess.run(["free", "-h"], capture_output=True, text=True)
print("=== RAM ===")
print(result.stdout)

# Check Ollama ps
req = urllib.request.Request("http://localhost:11434/api/ps")
resp = urllib.request.urlopen(req, timeout=10)
print("=== Ollama loaded models ===")
data = json.loads(resp.read())
print(json.dumps(data, indent=2))

# Check character 38 model
import sys
sys.path.insert(0, "/opt/clawfans/backend")
from models.database import SessionLocal, Character
db = SessionLocal()
c = db.query(Character).filter_by(id=38).first()
if c:
    print(f"\n=== Mistress V (id=38) ===")
    print(f"  name: {c.name}")
    model_attr = getattr(c, 'model', 'NO MODEL ATTR')
    print(f"  model: {model_attr}")
else:
    print("Character 38 not found")
