#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load database config
try:
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
except Exception as e:
    print(f"Error loading config: {e}")
    config = {}

database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
print(f"DATABASE_URL: {database_url}")

try:
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Import models after engine is created
    from main import User, Hive, Inspection
    
    db = SessionLocal()
    
    # Check what's in the database
    users = db.query(User).all()
    print(f"Found {len(users)} users:")
    for user in users:
        print(f"  User {user.id}: {user.email} (approved: {user.is_approved})")
    
    hives = db.query(Hive).all()
    print(f"Found {len(hives)} hives:")
    for hive in hives:
        print(f"  Hive {hive.id}: {hive.nickname} (user: {hive.user_id})")
    
    inspections = db.query(Inspection).all()
    print(f"Found {len(inspections)} inspections")
    
    db.close()
    
except Exception as e:
    print(f"Database error: {e}")
    import traceback
    traceback.print_exc()