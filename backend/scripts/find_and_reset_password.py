#!/usr/bin/env python3
"""
Find user by password hash and reset their password
"""

import sys
import os
import getpass

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import SessionLocal, User
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def main():
    # The hash you provided
    target_hash = "$2b$12$G4L8yGEfwWeBSia.c15P2uBqNIPng8HD3PNV0J684Y8MzxLiioCGG"
    
    db = SessionLocal()
    
    try:
        # Find user with this hash
        user = db.query(User).filter(User.password_hash == target_hash).first()
        
        if not user:
            print("❌ No user found with that password hash")
            print("\nAll users in database:")
            all_users = db.query(User).all()
            for u in all_users:
                print(f"  - {u.email} (ID: {u.id}, Admin: {u.is_admin}, Approved: {u.is_approved})")
            return
        
        print(f"✅ Found user: {user.email}")
        print(f"   User ID: {user.id}")
        print(f"   Admin: {user.is_admin}")
        print(f"   Approved: {user.is_approved}")
        print()
        
        # Get new password
        new_password = getpass.getpass("Enter new password: ").strip()
        if not new_password:
            print("❌ Password is required")
            return
        
        # Confirm
        confirm_password = getpass.getpass("Confirm new password: ").strip()
        if new_password != confirm_password:
            print("❌ Passwords don't match")
            return
        
        # Update password
        user.password_hash = pwd_context.hash(new_password)
        db.commit()
        
        print(f"✅ Password updated for {user.email}!")
        print(f"   New password hash: {user.password_hash}")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()



