import requests
import json

base_url = "http://127.0.0.1:8000"

def test_auth_and_circles():
    # Test auth endpoints first
    print("Testing authentication endpoints...")
    
    # Test auth status (should work without auth)
    response = requests.get(f"{base_url}/auth/status")
    print(f"GET /auth/status: {response.status_code} - {response.text}")
    
    # Test circles endpoint without auth (should get 401)
    response = requests.get(f"{base_url}/circles")
    print(f"GET /circles (no auth): {response.status_code} - {response.text}")
    
    # Test inspections endpoint without auth (should get 401)
    response = requests.get(f"{base_url}/inspections")
    print(f"GET /inspections (no auth): {response.status_code} - {response.text}")
    
    print("\nTo test further, we need a valid session. Let's check if there are any users in the database...")

if __name__ == "__main__":
    test_auth_and_circles()