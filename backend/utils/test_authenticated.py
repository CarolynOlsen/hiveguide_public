import requests
import json

base_url = "http://127.0.0.1:8000"

def test_with_auth():
    session = requests.Session()
    
    # Try to login with the admin user
    print("Testing login...")
    login_data = {
        "email": "admin@example.com",
        "password": "adminpw"  # Try adminpw first
    }
    
    # Try login
    response = session.post(f"{base_url}/login", json=login_data)
    print(f"Login attempt with 'adminpw': {response.status_code} - {response.text}")
    
    if response.status_code != 200:
        # If login failed, let's also try some other common passwords
        for password in ["test123", "admin", "password", "admin123"]:
            login_data["password"] = password
            response = session.post(f"{base_url}/login", json=login_data)
            print(f"Login with password '{password}': {response.status_code}")
            if response.status_code == 200:
                break
        else:
            print("All login attempts failed. Cannot test authenticated endpoints.")
            return
    
    print("Login successful! Testing authenticated endpoints...")
    
    # Test circles endpoint
    print("\nTesting /circles endpoint...")
    response = session.get(f"{base_url}/circles")
    print(f"GET /circles: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")
        # Check server logs for more details
        print("Check server logs for the exact error.")
    else:
        print(f"Success: {response.text}")
    
    # Test inspections endpoint  
    print("\nTesting /inspections endpoint...")
    response = session.get(f"{base_url}/inspections")
    print(f"GET /inspections: {response.status_code}")
    if response.status_code != 200:
        print(f"Error response: {response.text}")
    else:
        print(f"Success: {response.text}")

if __name__ == "__main__":
    test_with_auth()