#!/usr/bin/env python3
"""
Script to clear all existing hives and inspections.
Run this before populate_hives.py to start fresh.
"""

import os
import sys
import yaml
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path so we can import from main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import User, Hive, Inspection

def clear_hives():
    # Load config from parent directory
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        config = {}

    database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Get the admin user (assumes admin user exists)
        admin_user = db.query(User).filter(User.is_admin == True).first()
        if not admin_user:
            print("❌ No admin user found.")
            return
        
        print(f"👤 Using admin user: {admin_user.email}")
        
        # Count existing hives and inspections
        hive_count = db.query(Hive).filter(Hive.user_id == admin_user.id).count()
        inspection_count = db.query(Inspection).join(Hive).filter(Hive.user_id == admin_user.id).count()
        
        if hive_count == 0:
            print("✅ No hives found to delete.")
            return
        
        print(f"🔍 Found {hive_count} hives and {inspection_count} inspections")
        
        # Get hive IDs first, then delete inspections
        hive_ids = [hive.id for hive in db.query(Hive).filter(Hive.user_id == admin_user.id).all()]
        
        # Delete inspections for these hives
        deleted_inspections = db.query(Inspection).filter(Inspection.hive_id.in_(hive_ids)).delete(synchronize_session='fetch')
        print(f"🗑️  Deleted {deleted_inspections} inspections")
        
        # Delete all hives
        deleted_hives = db.query(Hive).filter(Hive.user_id == admin_user.id).delete()
        print(f"🗑️  Deleted {deleted_hives} hives")
        
        # Commit the changes
        db.commit()
        
        print(f"✅ Successfully cleared all data: {deleted_hives} hives and {deleted_inspections} inspections")
        
    except Exception as e:
        print(f"❌ Error clearing hives: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_hives()
