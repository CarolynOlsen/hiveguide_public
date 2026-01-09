#!/usr/bin/env python3
"""
Create a regular (non-admin) user for HiveScribe
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
    # Get the project root directory (parent of scripts/)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    
    print(f"Script directory: {script_dir}")
    print(f"Project root: {project_root}")
    
    # Add project root to Python path
    sys.path.insert(0, str(project_root))
    
    try:
        from main import User
        print("✅ Successfully imported User from main")
        return User, project_root
    except ImportError as e:
        print(f"❌ Failed to import from main: {e}")
        print(f"   Make sure you're running this from the hive_scribe project")
        print(f"   Current working directory: {os.getcwd()}")
        sys.exit(1)

def load_config(project_root):
    """Load database configuration"""
    config_path = project_root / "config.yaml"
    config = {}
    
    try:
        if config_path.exists():
            with open(config_path, "r") as f:
                config = yaml.safe_load(f) or {}
            print(f"✅ Loaded config from {config_path}")
        else:
            print(f"⚠️  No config.yaml found at {config_path}")
    except Exception as e:
        print(f"⚠️  Could not load config.yaml: {e}")
    
    database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
    
    if not database_url:
        print("❌ DATABASE_URL not found in environment or config.yaml")
        print("   Set DATABASE_URL environment variable or add to config.yaml")
        sys.exit(1)
    
    print(f"✅ Using database: {database_url[:50]}...")
    return database_url

def create_user(User, database_url, email=None, password=None):
    """Create a regular (non-admin) user"""
    
    print("\n🔧 Setting up database connection...")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print("✅ Database connection established")
    
    db = SessionLocal()
    
    try:
        # Get user input if not provided
        if not email:
            email = input("\nEnter email address: ").strip().lower()
        
        if not password:
            password = input("Enter password: ").strip()
            
        if not email or not password:
            print("❌ Email and password are required")
            return None, None
        
        print(f"\n🔍 Checking if user {email} already exists...")
        
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == email).first()
        if existing_user:
            print(f"❌ User already exists: {email}")
            return None, None
        
        print("✅ Email is available")
        print("🔐 Hashing password...")
        
        # Hash password
        hashed_password = pwd_context.hash(password)
        
        print("👤 Creating user record...")
        
        # Create regular user (not admin, approved by default)
        user = User(
            email=email,
            password_hash=hashed_password,
            is_admin=False,        # Regular user, not admin
            is_approved=True       # Auto-approve (change to False if you want manual approval)
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"✅ Created user: {email}")
        print(f"   User ID: {user.id}")
        print(f"   Admin: {user.is_admin}")
        print(f"   Approved: {user.is_approved}")
        
        return email, password
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error creating user: {e}")
        import traceback
        traceback.print_exc()
        return None, None
        
    finally:
        db.close()

def main():
    """Main function"""
    print("🐝 HiveScribe User Creation Script")
    print("=" * 40)
    
    # Setup imports and paths
    User, project_root = setup_imports()
    
    # Load configuration
    database_url = load_config(project_root)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Create a regular user account')
    parser.add_argument('--email', help='User email address')
    parser.add_argument('--password', help='User password')
    parser.add_argument('--batch', action='store_true', help='Batch mode - fail if email/password not provided')
    
    args = parser.parse_args()
    
    if args.batch and (not args.email or not args.password):
        print("❌ In batch mode, both --email and --password must be provided")
        sys.exit(1)
    
    # Create the user
    email, password = create_user(User, database_url, args.email, args.password)
    
    if email and password:
        print(f"\n🎉 User creation successful!")
        print(f"   Email: {email}")
        print(f"   Password: {password}")
        print(f"   Login URL: http://localhost:5173/")
    else:
        print("\n❌ User creation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()