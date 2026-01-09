import requests
import json

base_url = "http://127.0.0.1:8000"

def test_secure_sessions():
    print("=== Testing Secure Session Implementation ===")
    
    # Test 1: Login should work and create a proper session
    print("\n1. Testing login with secure session creation...")
    session = requests.Session()
    login_data = {"email": "admin@example.com", "password": "adminpw"}
    response = session.post(f"{base_url}/login", json=login_data)
    
    if response.status_code == 200:
        print("SUCCESS: Login worked")
        cookies = session.cookies.get_dict()
        session_token = cookies.get('session_id')
        if session_token and len(session_token) > 10:  # Should be a long random token
            print(f"SUCCESS: Got secure session token (length: {len(session_token)})")
        else:
            print(f"FAILED: Session token looks suspicious: {session_token}")
    else:
        print(f"FAILED: Login failed: {response.status_code} - {response.text}")
        return
    
    # Test 2: Test endpoint access with valid session
    print("\n2. Testing endpoint access with valid session...")
    response = session.get(f"{base_url}/circles")
    if response.status_code == 200:
        print("SUCCESS: /circles endpoint accessible with valid session")
    else:
        print(f"FAILED: /circles endpoint failed: {response.status_code} - {response.text}")
    
    # Test 3: Test auth/me endpoint
    print("\n3. Testing /auth/me endpoint...")
    response = session.get(f"{base_url}/auth/me")
    if response.status_code == 200:
        data = response.json()
        print(f"SUCCESS: /auth/me returned: {data}")
    else:
        print(f"FAILED: /auth/me failed: {response.status_code} - {response.text}")
    
    # Test 4: Try to impersonate with fake session
    print("\n4. Testing session impersonation prevention...")
    fake_session = requests.Session()
    fake_session.cookies.set('session_id', 'fake_token_123')
    response = fake_session.get(f"{base_url}/circles")
    if response.status_code == 401:
        print("SUCCESS: Fake session token rejected (401)")
    else:
        print(f"FAILED: Fake session token accepted! {response.status_code} - {response.text}")
    
    # Test 5: Try to impersonate with numeric user ID (old vulnerability)
    print("\n5. Testing old vulnerability (direct user ID impersonation)...")
    old_vuln_session = requests.Session()
    old_vuln_session.cookies.set('session_id', '1')  # Try to impersonate user 1
    response = old_vuln_session.get(f"{base_url}/circles")
    if response.status_code == 401:
        print("SUCCESS: Direct user ID impersonation prevented (401)")
    else:
        print(f"FAILED: Direct user ID impersonation worked! {response.status_code}")
    
    # Test 6: Test logout invalidation
    print("\n6. Testing session invalidation on logout...")
    response = session.post(f"{base_url}/logout")
    if response.status_code == 200:
        print("SUCCESS: Logout endpoint worked")
        
        # Try to access endpoint with invalidated session
        response = session.get(f"{base_url}/circles")
        if response.status_code == 401:
            print("SUCCESS: Session properly invalidated after logout")
        else:
            print(f"FAILED: Session still valid after logout: {response.status_code}")
    else:
        print(f"FAILED: Logout failed: {response.status_code} - {response.text}")
    
    print("\n=== Security Testing Complete ===")

if __name__ == "__main__":
    test_secure_sessions()