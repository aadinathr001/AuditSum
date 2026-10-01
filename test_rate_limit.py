import requests

BASE = "http://127.0.0.1:8000"
session = requests.Session()

session.post(f"{BASE}/auth/login", json={"email": "test@example.com", "password": "MyTestPassword123"})

for i in range(2):
    resp = session.post(f"{BASE}/documents/16/runs")  # use a real document_id you have
    print(f"call {i+1}: {resp.status_code}")