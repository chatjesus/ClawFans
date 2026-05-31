import requests
h = requests.get('http://127.0.0.1:8188/history?max_items=10', timeout=5).json()
for pid, data in list(h.items())[-2:]:
    msgs = data.get('status', {}).get('messages', [])
    for m in msgs:
        if isinstance(m, list) and len(m) > 1 and isinstance(m[1], dict) and 'execution_error' in str(m[0]):
            err = m[1]
            print(f"PID {pid[:8]}: node={err.get('node_type','?')} ({err.get('node_id','?')})")
            print(f"  msg: {err.get('exception_message','')[:200]}")
            tb = err.get('traceback', [])
            if tb:
                print(f"  trace: {tb[-1][:150]}")
