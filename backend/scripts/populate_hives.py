#!/usr/bin/env python3
"""
Script to populate hives and inspections based on existing data.
Creates hives with proper names and locations, plus their latest inspections.
"""

import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path so we can import from main
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.main import User, Hive, Inspection

def create_hives_and_inspections():
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
            print("❌ No admin user found. Please run create_admin.py first.")
            return
        
        print(f"👤 Using admin user: {admin_user.email}")
        
        # Define hive data based on screenshot
        hives_data = [
            {
                "nickname": "Hillcrest 1",
                "location": "Milwaukee", 
                "description": "Apimaye, Est. 5/19/2024",
                "inspections": [
                    {
                        "date": "2025-07-20",
                        "notes": "DOOM. We shook out the laying worker hive in the north garden and took their hive away. They flew around like a swarm and covered the patio."
                    }
                ]
            },
            {
                "nickname": "Hillcrest 2", 
                "location": "Milwaukee",
                "description": "Woodenware, Est. 7/3/2024",
                "inspections": [
                    {
                        "date": "2025-07-19",
                        "notes": "Split on one Queen. Lots of eggs. Limited room to lay. Too deep is mostly honey and another great laying pattern up and through both boxes. No queen or queen cells found. Building out swarm. On a frame of one, eggs and larvae. Good laying pattern on a fresh eggs Frames. Lots of reserves and should a couple swarm cells. dry. Opened 4 cupped swarm cells. Decided that's probably good. Look of all brood. Added 2nd deep that already had some factor and pollen. Room to lay. Eggs. Lots of goodies. Capped brood including drones. Brood comb from with 2 good general cells, made another one. We saw a couple queen cells."
                    },
                    {
                        "date": "2025-08-02",
                        "notes": "Took off super, brought it to Franksville #2. Applied Apiguard. Bees were fairly chill"
                    }
                ]
            },
            {
                "nickname": "Franksville 1",
                "location": "Franksville",
                "description": "South, Est. 6/2/2025",
                "inspections": [
                    {
                        "date": "2025-07-13",
                        "notes": "Saw queen and eggs. Limited room to lay. We added 2 supers. Good laying pattern except on 2 frames that were already drawn. Queen found. New queen but queen bee and yesterday. Two box top, first frames have capped resources. Capped brood on 5 frames, did not looking eggs and brood eggs and capped resources. Mostly adding a box for queen but there is good laying resources."
                    },
                    {
                        "date": "2025-07-31",
                        "notes": "Saw queen. A super is capped, 1 not. Varroa tested. Put a bee escape and a queen excluder under supers. Next steps, probably take the capped one home."
                    },
                    {
                        "date": "2025-08-09", 
                        "notes": "Saw queen. 1 super is capped, 1 not. Varroa tested. Put a bee escape and a queen excluder under the supers. Next steps: Go through the supers, probably take the capped one home."
                    }
                ]
            },
            {
                "nickname": "Franksville 2",
                "location": "Franksville",
                "description": "Middle, East, Est. 5/6/2025", 
                "inspections": [
                    {
                        "date": "2025-07-06",
                        "notes": "Starting to build out top box. Added hachert feeder for encouragement (enough production, bees eggs, very little room to lay because frames not built out). No queen cells and queen spotted."
                    },
                    {
                        "date": "2025-07-13",
                        "notes": "Lots of freshly drawn comb. Lots of capped honey and capped brood. Did see queen cells off boxes from top box."
                    },
                    {
                        "date": "2025-07-31",
                        "notes": "Saw eggs but not queen. Varroa tested. Next steps: Refill top feeder? It was ~2/3 full. Something we put in top deep and the bottom deep was queen right. We weren't able to get all the brood at the bottom kit, the bottom deep is contaminated a bit and with 2 supers so, that was good and we cut out."
                    },
                    {
                        "date": "2025-08-09",
                        "notes": "Swarmed, recently because we can see the swarm. We think they were too crowded after we put a bee escape on, on 8/7. We left a good capped queen cell and destroyed some others. Took off a super to take home, leaving them with 1 super. Next steps: We need to get some swiffer pads in there because we saw hive beetles."
                    }
                ]
            },
            {
                "nickname": "Franksville 3",
                "location": "Franksville", 
                "description": "North, Pine Tree Swarm, Est. 6/11/2025",
                "inspections": [
                    {
                        "date": "2025-07-13",
                        "notes": "Did not see Queen. Lots of eggs. Limited room to lay. Too deep is mostly honey and another, great laying pattern up and through both boxes. No queen or queen cells found. Building"
                    },
                    {
                        "date": "2025-07-31",
                        "notes": "Saw eggs but not queen. Varroa tested."
                    },
                    {
                        "date": "2025-08-09",
                        "notes": "Saw eggs but not queen. Varroa tested. Next steps: Refill top feeder? It was ~2/3 full."
                    }
                ]
            },
            {
                "nickname": "Franksville 4",
                "location": "Franksville",
                "description": "Back, Leonard Swarm, Est. 6/17/2025",
                "inspections": [
                    {
                        "date": "2025-07-18",
                        "notes": "They are building bottom line found nine eggs and larvae. 2 frames added with empty brood to help build out new comb. Just started new comb with honey. Top box all nectar and honey. Bottom box found nine eggs and larvae."
                    },
                    {
                        "date": "2025-07-31",
                        "notes": "Saw queen and a box feeder. Top eggs lots of nectar and honey with good water with nectar and a little capped brood. Top deep lots of nectar and honey. Bottom box we found eggs, right away, good pattern."
                    },
                    {
                        "date": "2025-08-09", 
                        "notes": "Saw queen, eggs, lots of resources. Weight 95 lbs. mite tested 2 varroa. Transferred into Apimaye for later transfer to MKE. 2 empty queen cups. We transferred a super onto the hive, but it's a wood one. Next steps: Swap the super into an Apimaye box. Refill frame feeder?"
                    }
                ]
            },
            {
                "nickname": "Franksville 5",
                "location": "Franksville",
                "description": "Tree, Split from Fr #1, Est. 6/27/2025",
                "inspections": [
                    {
                        "date": "2025-07-18",
                        "notes": "Split up laying workers. Lots of capped drone brood. Multiple eggs per cell. Lots population. They'd taken laying workers frames are good and probably it is in the bottom, reorganized. To put on the ground. Queen excluder is to get them eggs and maybe that is the brood on couple or so maybe 2-3 frames that were already drawn."
                    },
                    {
                        "date": "2025-07-20",
                        "notes": "DOOM. We shook out the laying worker hive in the north garden and took their hive away. They flew around like a swarm and covered the patio."
                    },
                    {
                        "date": "2025-07-25",
                        "notes": "Very fresh eggs, top box. At Least 5 frames built out. Possibly getting being bound and capped brood on at least that much. This looks like the house of queen. Refilled"
                    },
                    {
                        "date": "2025-08-09",
                        "notes": "Were going to add a 2nd deep but instead gave it to swarm. Left them with a partially full frame feeder above the inner cover. Next steps: Get them a 2nd deep. Feed."
                    }
                ]
            },
            {
                "nickname": "Franksville 6",
                "location": "Franksville", 
                "description": "aka 1.5, Est. 7/12/2025",
                "inspections": [
                    {
                        "date": "2025-08-07",
                        "notes": "Transferred into a single deep. Included 2 empty frames with 2 fully capped frames from #2. Next steps: Normal inspection."
                    }
                ]
            },
            {
                "nickname": "Franksville 7",
                "location": "Franksville",
                "description": "aka 2.5, Est. 8/9/2025", 
                "inspections": [
                    {
                        "date": "2025-08-09",
                        "notes": "Established from a swarm out of Franksville #2. Given empty frames. Next steps: Check if queen right after we're back from Canada. (Beekeeper's Handbook says wait 7-10 days, OR state beekeeper's assoc says 2 weeks.)"
                    }
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
                Hive.user_id == admin_user.id
            ).first()
            
            if existing_hive:
                print(f"🏠 Hive '{hive_data['nickname']}' already exists, skipping...")
                continue
            
            # Create hive
            hive = Hive(
                nickname=hive_data["nickname"],
                location=hive_data["location"],
                description=hive_data["description"],
                user_id=admin_user.id
            )
            
            db.add(hive)
            db.flush()  # Get the hive ID
            
            # Create all inspections for this hive
            for inspection_data in hive_data["inspections"]:
                inspection_date = datetime.strptime(inspection_data["date"], "%Y-%m-%d")
                notes = inspection_data["notes"]
                
                # Parse queen and eggs visibility from notes
                queen_visible = True if "queen" in notes.lower() else None
                eggs_visible = True if "eggs" in notes.lower() else None
                
                inspection = Inspection(
                    hive_id=hive.id,
                    timestamp=inspection_date,
                    notes=notes,
                    transcription=None,  # No transcription data
                    weather=None,  # No weather data
                    temperature=None,  # No temperature data
                    queen_visible=queen_visible,
                    eggs_visible=eggs_visible,
                    larvae_visible=None,  # No larvae data
                    capped_brood_visible=None,  # No capped brood data
                    laying_pattern=None,  # No laying pattern data
                    activity_level=None,  # No activity level data
                    photos=None  # No photos
                )
                
                db.add(inspection)
                created_inspections.append(f"{hive.nickname} - {inspection_data['date']}")
            
            created_hives.append(hive.nickname)
            
            print(f"✅ Created hive: {hive.nickname} ({hive.location}) - {hive.description}")
            print(f"   📝 Added {len(hive_data['inspections'])} inspections")
        
        # Commit all changes
        db.commit()
        
        print(f"\n🎉 Successfully created:")
        print(f"   🏠 {len(created_hives)} hives")
        print(f"   📝 {len(created_inspections)} inspections")
        
        if created_hives:
            print(f"\nCreated hives:")
            for hive_name in created_hives:
                print(f"   - {hive_name}")
        
        return created_hives, created_inspections
        
    except Exception as e:
        print(f"❌ Error creating hives and inspections: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_hives_and_inspections()
