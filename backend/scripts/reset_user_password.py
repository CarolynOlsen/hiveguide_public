#!/usr/bin/env python3
"""
Reset a user's password by email
"""

import sys
import os

# Add project root to path (go up from backend/scripts/ to project root)
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(script_dir)
project_root = os.path.dirname(backend_dir)
sys.path.insert(0, project_root)

from backend.main import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def reset_password(email, new_password):
    db = SessionLocal()
    
    try:
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            print(f"❌ User not found: {email}")
            return False
        
        print(f"✅ Found user: {email}")
        print(f"   User ID: {user.id}")
        print(f"   Admin: {user.is_admin}")
        print(f"   Approved: {user.is_approved}")
        
        # Update password
        user.password_hash = pwd_context.hash(new_password)
        db.commit()
        
        print(f"✅ Password updated for {email}!")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) == 3:
        email = sys.argv[1]
        password = sys.argv[2]
    else:
        print("Usage: python reset_user_password.py <email> <new_password>")
        sys.exit(1)
    
    success = reset_password(email, password)
    sys.exit(0 if success else 1)

