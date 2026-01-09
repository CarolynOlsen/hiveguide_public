#!/usr/bin/env python3
"""
Script to populate test account data for HiveGuide demo.
Creates test@test.com user with 4 hives and inspection history.
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext

# Add project root to path so we can import from backend
script_dir = Path(__file__).resolve().parent
backend_dir = script_dir.parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

from backend.main import User, Hive, Inspection

def populate_test_data():
    """Create test user and populate with demo data"""
    
    # Load config from backend directory
    script_dir = Path(__file__).resolve().parent
    backend_dir = script_dir.parent
    project_root = backend_dir.parent
    config_path = project_root / "config.yaml"
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        config = {}

    database_url = os.environ.get("DATABASE_URL") or config.get("database_url")
    if not database_url:
        print("❌ DATABASE_URL not found in environment or config.yaml")
        sys.exit(1)
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    db = SessionLocal()
    
    try:
        # Check if test user already exists and clean up if found
        test_email = "testuser@example.com"
        test_password = "test123"
        
        existing_user = db.query(User).filter(User.email == test_email).first()
        
        if existing_user:
            print(f"🗑️  Found existing test user '{test_email}' - cleaning up old data...")
            # Delete sessions first to avoid foreign key constraint
            db.execute(text("DELETE FROM sessions WHERE user_id = :user_id"), {"user_id": existing_user.id})
            # Delete user (cascades to hives and inspections)
            db.delete(existing_user)
            db.commit()
            print(f"✅ Deleted old test data")
        
        # Create test user
        hashed_password = pwd_context.hash(test_password)
        test_user = User(
            email=test_email,
            password_hash=hashed_password,
            is_admin=False,
            is_approved=True  # Pre-approve for testing
        )
        db.add(test_user)
        db.flush()
        print(f"✅ Created test user: {test_email}")
        print(f"   Password: {test_password}")
        
        # Define hive data with unique inspection histories
        hives_data = [
            {
                "nickname": "Home 1",
                "location": "Backyard",
                "description": "Original hive established in Spring 2025. Strong colony with consistent production.",
                "start_year": 2025,
                "start_month": 4,  # April
                "inspections": [
                    {"month": 4, "weather": "partly cloudy", "temp": "55°F", "activity": "moderate",
                     "notes": "Package installed. Queen in cage, will check for release in 3 days. Bees clustering and beginning to explore. Started feeding 1:1 syrup; bees are taking it well.",
                     "action_items": [{"description": "Check queen release in 3 days", "priority": "normal"}]},
                    {"month": 5, "weather": "sunny", "temp": "68°F", "activity": "high",
                     "notes": "Found the queen on frame 4! Good laying pattern, 6 frames of brood now. Lots of pollen coming in - mostly yellow and orange. Building up fast."},
                    {"month": 6, "weather": "sunny", "temp": "78°F", "activity": "very high",
                     "notes": "Added 2nd deep box, they need the space. 8 frames of solid brood. Put on first super."},
                    {"month": 7, "weather": "hot and humid", "temp": "85°F", "activity": "high",
                     "notes": "Both brood boxes full. Marked queen with blue dot. First super about 60% full so added a second one. Tons of nectar coming in."},
                    {"month": 8, "weather": "sunny", "temp": "82°F", "activity": "high",
                     "notes": "Pulled full super for extraction; did not extract from brood frames. Queen still laying on 7 frames. Top super mostly capped. Looking good."},
                    {"month": 9, "weather": "mild", "temp": "70°F", "activity": "moderate",
                     "notes": "Brood down to 5 frames. Took off the supers. Heavy frames of honey in top deep. No disease. Ready for winter."},
                    {"month": 10, "weather": "cool", "temp": "58°F", "activity": "low",
                     "notes": "Wrapped for winter. Reduced to 2 deeps. Entrance reducer in. Measured hive weight: 110 lbs (target 100–120 lbs for 2 deeps). Should be good for winter."}
                ]
            },
            {
                "nickname": "Home 2",
                "location": "Backyard", 
                "description": "Swarm caught from Home 1 in June 2025. Growing colony with excellent temperament.",
                "start_year": 2025,
                "start_month": 6,  # June - starts later
                "inspections": [
                    {"month": 6, "weather": "sunny", "temp": "78°F", "activity": "moderate",
                     "notes": "Caught the swarm from Home 1! Hived them in new woodenware. About 3 lbs of bees, maybe more. Super calm. Already drawing comb."},
                    {"month": 7, "weather": "hot and humid", "temp": "85°F", "activity": "high",
                     "notes": "Saw queen laying! 4 frames with eggs and larvae. Comb building out nice. Fed them to help build up faster."},
                    {"month": 8, "weather": "sunny", "temp": "82°F", "activity": "high",
                     "notes": "Growing like crazy. 6 frames of brood. Added the second deep today. Storing nectar in top box."},
                    {"month": 9, "weather": "mild", "temp": "70°F", "activity": "moderate",
                     "notes": "Still building. Queen laying on 5 frames. Good stores of pollen and some honey. Think they'll make it through winter."},
                    {"month": 10, "weather": "cool", "temp": "58°F", "activity": "low",
                     "notes": "Not seeing any signs of queen, and there are charged queen cells. Uh oh -- it's late in the season for a queen to mate. Need to come back in a few days to check. Hive weight 80 lbs, for 2 deeps. Fed syrup 2:1.",
                     "action_items": [{"description": "Check for queen and eggs", "priority": "high", "timeframe_days": 7}]}
                ]
            },
            {
                "nickname": "Bee Club 1",
                "location": "Club Bee Yard",
                "description": "Hive maintained at local bee club. Great for learning and sharing experiences.",
                "start_year": 2025,
                "start_month": 4,  # April
                "inspections": [
                    {"month": 4, "weather": "partly cloudy", "temp": "55°F", "activity": "moderate",
                     "notes": "Made it through winter! Saw queen on frame 2. 4 frames of brood. Reversed the boxes. Looking good for spring."},
                    {"month": 5, "weather": "sunny", "temp": "68°F", "activity": "high",
                     "notes": "Building up fast. 7 frames of brood - eggs, larvae, capped. Found one queen cell and squashed it. Added a super. Really active."},
                    {"month": 6, "weather": "sunny", "temp": "78°F", "activity": "very high",
                     "notes": "Checked for swarm cells - didn't find any. Both deeps full of bees. Added 2nd super. Big nectar flow on."},
                    {"month": 7, "weather": "hot and humid", "temp": "85°F", "activity": "high",
                     "notes": "Huge population. Queen still laying great. First super mostly capped. Used this hive to demo frame inspection at club meeting. Super gentle."},
                    {"month": 8, "weather": "sunny", "temp": "82°F", "activity": "high",
                     "notes": "Pulled full super for extraction at club meeting (yield: 75 lbs). Brood on 6 frames. Queen still going. Supers not returned after August."},
                    {"month": 9, "weather": "mild", "temp": "70°F", "activity": "moderate",
                     "notes": "Brood down to 4 frames. Top box heavy with honey. Reversed boxes for winter setup. No signs of disease or pests."},
                    {"month": 10, "weather": "cool", "temp": "58°F", "activity": "low",
                     "notes": "Alcohol wash: 10 mites per 300 bees (3%). Above threshold -- need to come back and treat. Good stores though; hive weight 110.",
                     "action_items": [{"description": "Treat for varroa mites", "priority": "high", "timeframe_days": 3}]}
                ]
            },
            {
                "nickname": "Bee Club 2",
                "location": "Club Bee Yard",
                "description": "Second hive at bee club. Used for demonstrating inspection techniques.",
                "start_year": 2025,
                "start_month": 4,  # April
                "inspections": [
                    {"month": 4, "weather": "partly cloudy", "temp": "55°F", "activity": "moderate",
                     "notes": "Installed the nuc today. 5 frames with a laying queen. Good brood pattern. Bees orienting well."},
                    {"month": 5, "weather": "sunny", "temp": "68°F", "activity": "high",
                     "notes": "Building up good. 6 frames of brood. Added 2nd box. Found the queen pretty easy - not marked yet. Used for queen finding demo at club."},
                    {"month": 6, "weather": "sunny", "temp": "78°F", "activity": "very high",
                     "notes": "Found 2 swarm cells! Getting crowded. Added a super and gave them more space. Marked queen with white during club meeting."},
                    {"month": 7, "weather": "hot and humid", "temp": "85°F", "activity": "high",
                     "notes": "Did a split to prevent swarming. Strong hive. 7 frames brood. Super getting filled. Did frame inspection demo with new beekeepers."},
                    {"month": 8, "weather": "sunny", "temp": "82°F", "activity": "high",
                     "notes": "Noticed spotty brood pattern on 3 frames, possible varroa. Queen still laying on 6 frames. Super about half full."},
                    {"month": 9, "weather": "mild", "temp": "70°F", "activity": "moderate",
                     "notes": "Brood down to 5 frames. Spotty pattern persists; possible causes include mites (uncapping cells) or weak queen. Removed super. Will perform mite test next inspection.",
                     "action_items": [{"description": "Perform mite test and assess queen", "priority": "medium", "timeframe_days": 7}]},
                    {"month": 10, "weather": "cool", "temp": "58°F", "activity": "low",
                     "notes": "Alcohol wash: 13 mites per 300 bees (4%). Well above threshold; applied oxalic acid treatment. Population still decent despite mite pressure.",
                     "action_items": [{"description": "Monitor mite levels after treatment", "priority": "medium", "timeframe_days": 14}]}
                ]
            }
        ]
        
        created_hives = []
        created_inspections = []
        
        # Create hives and inspections
        for hive_data in hives_data:
            # Check if hive already exists
            existing_hive = db.query(Hive).filter(
                Hive.nickname == hive_data["nickname"],
                Hive.user_id == test_user.id
            ).first()
            
            if existing_hive:
                print(f"🏠 Hive '{hive_data['nickname']}' already exists, skipping...")
                continue
            
            # Create hive
            hive = Hive(
                nickname=hive_data["nickname"],
                location=hive_data["location"],
                description=hive_data["description"],
                user_id=test_user.id
            )
            
            db.add(hive)
            db.flush()  # Get the hive ID
            
            # Create inspections from the predefined data
            for inspection_data in hive_data["inspections"]:
                month = inspection_data["month"]
                # Create inspection date 
                inspection_date = datetime(hive_data["start_year"], month, 5, 14, 30)

                notes = inspection_data["notes"]
                
                # Parse some data from notes for database fields
                queen_visible = "queen" in notes.lower() and ("spotted" in notes.lower() or "marked" in notes.lower())
                eggs_visible = "eggs" in notes.lower() or "laying" in notes.lower()
                larvae_visible = "larvae" in notes.lower()
                capped_brood_visible = "brood" in notes.lower() and "capped" in notes.lower()
                
                # Determine laying pattern
                if "spotty" in notes.lower():
                    laying_pattern = "spotty"
                elif eggs_visible:
                    laying_pattern = "solid"
                else:
                    laying_pattern = None
                
                inspection = Inspection(
                    hive_id=hive.id,
                    timestamp=inspection_date,
                    notes=notes,
                    weather=inspection_data["weather"],
                    temperature=inspection_data["temp"],
                    queen_visible=queen_visible,
                    eggs_visible=eggs_visible,
                    larvae_visible=larvae_visible,
                    capped_brood_visible=capped_brood_visible,
                    laying_pattern=laying_pattern,
                    activity_level=inspection_data["activity"],
                    action_items=inspection_data.get("action_items")
                )
                
                db.add(inspection)
                created_inspections.append(f"{hive.nickname} - {inspection_date.strftime('%Y-%m-%d')}")
            
            created_hives.append(hive.nickname)
            
            print(f"✅ Created hive: {hive.nickname} ({hive.location})")
            print(f"   📝 Added {len(hive_data['inspections'])} inspections")
        
        # Commit all changes
        db.commit()
        
        print(f"\n🎉 Successfully created:")
        print(f"   👤 Test user: {test_email}")
        print(f"   🏠 {len(created_hives)} hives")
        print(f"   📝 {len(created_inspections)} inspections")
        
        if created_hives:
            print(f"\nCreated hives:")
            for hive_name in created_hives:
                print(f"   - {hive_name}")
        
        print(f"\n🔑 Login credentials:")
        print(f"   Email: {test_email}")
        print(f"   Password: {test_password}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
        
    finally:
        db.close()

def main():
    """Main function"""
    print("🐝 HiveGuide Test Data Population")
    print("=" * 50)
    
    success = populate_test_data()
    
    if success:
        print(f"\n✅ Test data population completed successfully!")
    else:
        print(f"\n❌ Test data population failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
