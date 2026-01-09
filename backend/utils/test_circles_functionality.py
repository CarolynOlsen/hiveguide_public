import requests
import json

base_url = "http://127.0.0.1:8000"

def test_circles_full_functionality():
    session = requests.Session()
    
    # Login
    login_data = {"email": "admin@example.com", "password": "adminpw"}
    response = session.post(f"{base_url}/login", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.status_code}")
        return
    
    print("SUCCESS: Login successful")
    
    # Test creating a circle
    print("\nTesting circle creation...")
    circle_data = {"name": "Test Circle", "description": "A test circle for hive sharing"}
    response = session.post(f"{base_url}/circles", json=circle_data)
    print(f"Create circle: {response.status_code}")
    if response.status_code == 200:
        circle = response.json()
        circle_id = circle["id"]
        print(f"SUCCESS: Circle created: {circle}")
    else:
        print(f"FAILED: Failed to create circle: {response.text}")
        return
    
    # Test listing circles
    print("\nTesting circle listing...")
    response = session.get(f"{base_url}/circles")
    print(f"List circles: {response.status_code}")
    if response.status_code == 200:
        circles = response.json()
        print(f"SUCCESS: Circles listed: {circles}")
    else:
        print(f"FAILED: Failed to list circles: {response.text}")
    
    # Test inspections (should still work)
    print("\nTesting inspections...")
    response = session.get(f"{base_url}/inspections")
    print(f"List inspections: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: Inspections endpoint working")
    else:
        print(f"FAILED: Failed to get inspections: {response.text}")
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    test_circles_full_functionality()