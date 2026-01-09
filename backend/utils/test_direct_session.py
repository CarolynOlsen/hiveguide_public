#!/usr/bin/env python3

# Simple test to verify session functionality works
import sys
import os
import secrets
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import SessionLocal, Session, User, create_session, validate_session

def test_direct_session():
    db = SessionLocal()
    
    try:
        # Get a user
        user = db.query(User).filter(User.email == "admin@example.com").first()
        if not user:
            print("ERROR: Admin user not found")
            return
        
        print(f"Found user: {user.email}, ID: {user.id}")
        
        # Test creating a session
        print("Creating session...")
        session_token = create_session(user.id, db)
        print(f"Session token created: {session_token[:10]}...")
        
        # Test validating session
        print("Validating session...")
        validated_user = validate_session(session_token, db)
        if validated_user:
            print(f"SUCCESS: Session validation returned user {validated_user.email}")
        else:
            print("FAILED: Session validation returned None")
        
        # Test with fake session
        print("Testing fake session...")
        fake_user = validate_session("fake_token_123", db)
        if fake_user:
            print("FAILED: Fake session was validated!")
        else:
            print("SUCCESS: Fake session was rejected")
    
    finally:
        db.close()

if __name__ == "__main__":
    test_direct_session()