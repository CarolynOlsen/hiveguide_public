#!/usr/bin/env python3
"""
Reset admin user password for HiveGuide
"""

import os
import sys
import yaml
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

def setup_imports():
    """Setup imports and paths"""
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    sys.path.insert(0, str(project_root))
    
    try:
        from main import User
        return User, project_root
    except ImportError as e:
        print(f"❌ Failed to import from main: {e}")
        sys.exit(1)

def load_config(project_root):
    """Load database configuration"""
    config_path = project_root / "config.yaml"
    config = {}
    
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
    except Exception as e:
        pass
    
    database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment or config.yaml")
        sys.exit(1)
    
    return database_url

def reset_admin_password(User, database_url, email=None, new_password=None):
    """Reset admin user password"""
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    db = SessionLocal()
    
    try:
        # Get admin email if not provided
        if not email:
            print("Current admin users:")
            admins = db.query(User).filter(User.is_admin == True).all()
            for i, admin in enumerate(admins, 1):
                print(f"  {i}. {admin.email}")
            
            if len(admins) == 1:
                email = admins[0].email
                print(f"\nUsing: {email}")
            else:
                email = input("\nEnter admin email to reset: ").strip().lower()
        
        # Get new password if not provided
        if not new_password:
            new_password = input("Enter new password: ").strip()
            
        if not email or not new_password:
            print("❌ Email and password are required")
            return False
        
        # Find the admin user
        admin_user = db.query(User).filter(User.email == email).first()
        if not admin_user:
            print(f"❌ User not found: {email}")
            return False
        
        if not admin_user.is_admin:
            print(f"❌ User {email} is not an admin")
            return False
        
        # Update password
        hashed_password = pwd_context.hash(new_password)
        admin_user.password_hash = hashed_password
        
        db.commit()
        
        print(f"✅ Password updated for admin: {email}")
        print(f"   New password: {new_password}")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error updating password: {e}")
        return False
        
    finally:
        db.close()

def main():
    """Main function"""
    print("🔐 HiveGuide Admin Password Reset")
    print("=" * 40)
    
    # Setup imports and paths
    User, project_root = setup_imports()
    
    # Load configuration
    database_url = load_config(project_root)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Reset admin user password')
    parser.add_argument('--email', help='Admin email address')
    parser.add_argument('--password', help='New password')
    
    args = parser.parse_args()
    
    # Reset the password
    success = reset_admin_password(User, database_url, args.email, args.password)
    
    if success:
        print(f"\n🎉 Admin password reset successful!")
        print(f"   Login URL: http://localhost:5173/")
    else:
        print("\n❌ Password reset failed")
        sys.exit(1)

if __name__ == "__main__":
    main()