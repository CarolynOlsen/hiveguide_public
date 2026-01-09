import requests
import json

base_url = "http://127.0.0.1:8000"

def test_circle_deletion():
    session = requests.Session()
    
    # Login
    login_data = {"email": "admin@example.com", "password": "adminpw"}
    response = session.post(f"{base_url}/login", json=login_data)
    if response.status_code != 200:
        print(f"Login failed: {response.status_code}")
        return
    
    print("SUCCESS: Login successful")
    
    # Create a test circle to delete
    print("\nCreating test circle...")
    circle_data = {"name": "Test Delete Circle", "description": "A circle to test deletion"}
    response = session.post(f"{base_url}/circles", json=circle_data)
    if response.status_code != 200:
        print(f"FAILED: Could not create test circle: {response.text}")
        return
    
    circle = response.json()
    circle_id = circle["id"]
    print(f"SUCCESS: Created circle with ID {circle_id}: {circle['name']}")
    
    # List circles to confirm it exists
    print("\nListing circles before deletion...")
    response = session.get(f"{base_url}/circles")
    if response.status_code == 200:
        circles = response.json()
        print(f"SUCCESS: Found {len(circles)} circles")
        for c in circles:
            print(f"  - {c['id']}: {c['name']}")
    
    # Delete the circle
    print(f"\nDeleting circle {circle_id}...")
    response = session.delete(f"{base_url}/circles/{circle_id}")
    print(f"Delete response: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"SUCCESS: {result['message']}")
    else:
        print(f"FAILED: {response.text}")
        return
    
    # List circles to confirm it's deleted
    print("\nListing circles after deletion...")
    response = session.get(f"{base_url}/circles")
    if response.status_code == 200:
        circles = response.json()
        print(f"SUCCESS: Found {len(circles)} circles")
        for c in circles:
            print(f"  - {c['id']}: {c['name']}")
    
    # Try to delete a non-existent circle (should fail)
    print(f"\nTrying to delete non-existent circle...")
    response = session.delete(f"{base_url}/circles/99999")
    print(f"Delete non-existent response: {response.status_code}")
    if response.status_code == 404:
        print("SUCCESS: Correctly returned 404 for non-existent circle")
    else:
        print(f"UNEXPECTED: Expected 404, got {response.status_code}: {response.text}")
    
    print("\nCircle deletion tests completed!")

if __name__ == "__main__":
    test_circle_deletion()