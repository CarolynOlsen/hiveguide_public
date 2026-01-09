#!/usr/bin/env python3
"""
Seed a validation test user with realistic hives and inspections.

Usage:
  python -m validation.seed_validation_data --email <user> --password <pw> [--reseed]

Defaults mirror backend/scripts/populate_test_data.py but let you pick the user credentials
so validation runs can target a specific account.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import text
from passlib.context import CryptContext

# Add project root to path for imports
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from validation.services.db import User, Hive, Inspection, SessionLocal


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def ensure_user(db, email: str, password: str, reseed: bool) -> User:
    email = email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()

    if existing and reseed:
        # Clean existing user, sessions, and cascade deletes
        db.execute(text("DELETE FROM sessions WHERE user_id = :uid"), {"uid": existing.id})
        db.delete(existing)
        db.commit()
        existing = None

    if existing:
        return existing

    user = User(
        email=email,
        password_hash=pwd_context.hash(password),
        is_admin=False,
        is_approved=True,  # pre-approve for validation
    )
    db.add(user)
    db.flush()
    return user


# Reuse the rich hive/inspection set from populate_test_data.py
HIVES_DATA = [
    {
        "nickname": "Home 1",
        "location": "Backyard",
        "description": "Original hive established in Spring 2025. Strong colony with consistent production.",
        "start_year": 2025,
        "start_month": 4,
        "inspections": [
            {
                "month": 4,
                "weather": "partly cloudy",
                "temp": "55°F",
                "activity": "moderate",
                "notes": "Package installed. Queen in cage, will check for release in 3 days. Bees clustering and beginning to explore. Started feeding 1:1 syrup; bees are taking it well.",
                "action_items": [{"description": "Check queen release in 3 days", "priority": "normal"}],
            },
            {
                "month": 5,
                "weather": "sunny",
                "temp": "68°F",
                "activity": "high",
                "notes": "Found the queen on frame 4! Good laying pattern, 6 frames of brood now. Lots of pollen coming in - mostly yellow and orange. Building up fast.",
            },
            {
                "month": 6,
                "weather": "sunny",
                "temp": "78°F",
                "activity": "very high",
                "notes": "Added 2nd deep box, they need the space. 8 frames of solid brood. Put on first super.",
            },
            {
                "month": 7,
                "weather": "hot and humid",
                "temp": "85°F",
                "activity": "high",
                "notes": "Both brood boxes full. Marked queen with blue dot. First super about 60% full so added a second one. Tons of nectar coming in.",
            },
            {
                "month": 8,
                "weather": "sunny",
                "temp": "82°F",
                "activity": "high",
                "notes": "Pulled full super for extraction; did not extract from brood frames. Queen still laying on 7 frames. Top super mostly capped. Looking good.",
            },
            {
                "month": 9,
                "weather": "mild",
                "temp": "70°F",
                "activity": "moderate",
                "notes": "Brood down to 5 frames. Took off the supers. Heavy frames of honey in top deep. No disease. Ready for winter.",
            },
            {
                "month": 10,
                "weather": "cool",
                "temp": "58°F",
                "activity": "low",
                "notes": "Wrapped for winter. Reduced to 2 deeps. Entrance reducer in. Measured hive weight: 110 lbs (target 100–120 lbs for 2 deeps). Should be good for winter.",
            },
        ],
    },
    {
        "nickname": "Home 2",
        "location": "Backyard",
        "description": "Swarm caught from Home 1 in June 2025. Growing colony with excellent temperament.",
        "start_year": 2025,
        "start_month": 6,
        "inspections": [
            {
                "month": 6,
                "weather": "sunny",
                "temp": "78°F",
                "activity": "moderate",
                "notes": "Caught the swarm from Home 1! Hived them in new woodenware. About 3 lbs of bees, maybe more. Super calm. Already drawing comb.",
            },
            {
                "month": 7,
                "weather": "hot and humid",
                "temp": "85°F",
                "activity": "high",
                "notes": "Saw queen laying! 4 frames with eggs and larvae. Comb building out nice. Fed them to help build up faster.",
            },
            {
                "month": 8,
                "weather": "sunny",
                "temp": "82°F",
                "activity": "high",
                "notes": "Growing like crazy. 6 frames of brood. Added the second deep today. Storing nectar in top box.",
            },
            {
                "month": 9,
                "weather": "mild",
                "temp": "70°F",
                "activity": "moderate",
                "notes": "Still building. Queen laying on 5 frames. Good stores of pollen and some honey. Think they'll make it through winter.",
            },
            {
                "month": 10,
                "weather": "cool",
                "temp": "58°F",
                "activity": "low",
                "notes": "Not seeing any signs of queen, and there are charged queen cells. Uh oh -- it's late in the season for a queen to mate. Need to come back in a few days to check. Hive weight 80 lbs, for 2 deeps. Fed syrup 2:1.",
                "action_items": [
                    {"description": "Check for queen and eggs", "priority": "high", "timeframe_days": 7},
                ],
            },
        ],
    },
    {
        "nickname": "Bee Club 1",
        "location": "Club Bee Yard",
        "description": "Hive maintained at local bee club. Great for learning and sharing experiences.",
        "start_year": 2025,
        "start_month": 4,
        "inspections": [
            {
                "month": 4,
                "weather": "partly cloudy",
                "temp": "55°F",
                "activity": "moderate",
                "notes": "Made it through winter! Saw queen on frame 2. 4 frames of brood. Reversed the boxes. Looking good for spring.",
            },
            {
                "month": 5,
                "weather": "sunny",
                "temp": "68°F",
                "activity": "high",
                "notes": "Building up fast. 7 frames of brood - eggs, larvae, capped. Found one queen cell and squashed it. Added a super. Really active.",
            },
            {
                "month": 6,
                "weather": "sunny",
                "temp": "78°F",
                "activity": "very high",
                "notes": "Checked for swarm cells - didn't find any. Both deeps full of bees. Added 2nd super. Big nectar flow on.",
            },
            {
                "month": 7,
                "weather": "hot and humid",
                "temp": "85°F",
                "activity": "high",
                "notes": "Huge population. Queen still laying great. First super mostly capped. Used this hive to demo frame inspection at club meeting. Super gentle.",
            },
            {
                "month": 8,
                "weather": "sunny",
                "temp": "82°F",
                "activity": "high",
                "notes": "Pulled full super for extraction at club meeting (yield: 75 lbs). Brood on 6 frames. Queen still going. Supers not returned after August.",
            },
            {
                "month": 9,
                "weather": "mild",
                "temp": "70°F",
                "activity": "moderate",
                "notes": "Brood down to 4 frames. Top box heavy with honey. Reversed boxes for winter setup. No signs of disease or pests.",
            },
            {
                "month": 10,
                "weather": "cool",
                "temp": "58°F",
                "activity": "low",
                "notes": "Alcohol wash: 10 mites per 300 bees (3%). Above threshold -- need to come back and treat. Good stores though; hive weight 110.",
                "action_items": [{"description": "Treat for varroa mites", "priority": "high", "timeframe_days": 3}],
            },
        ],
    },
    {
        "nickname": "Bee Club 2",
        "location": "Club Bee Yard",
        "description": "Second hive at bee club. Used for demonstrating inspection techniques.",
        "start_year": 2025,
        "start_month": 4,
        "inspections": [
            {
                "month": 4,
                "weather": "partly cloudy",
                "temp": "55°F",
                "activity": "moderate",
                "notes": "Installed the nuc today. 5 frames with a laying queen. Good brood pattern. Bees orienting well.",
            },
            {
                "month": 5,
                "weather": "sunny",
                "temp": "68°F",
                "activity": "high",
                "notes": "Building up good. 6 frames of brood. Added 2nd box. Found the queen pretty easy - not marked yet. Used for queen finding demo at club.",
            },
            {
                "month": 6,
                "weather": "sunny",
                "temp": "78°F",
                "activity": "very high",
                "notes": "Found 2 swarm cells! Getting crowded. Added a super and gave them more space. Marked queen with white during club meeting.",
            },
            {
                "month": 7,
                "weather": "hot and humid",
                "temp": "85°F",
                "activity": "high",
                "notes": "Did a split to prevent swarming. Strong hive. 7 frames brood. Super getting filled. Did frame inspection demo with new beekeepers.",
            },
            {
                "month": 8,
                "weather": "sunny",
                "temp": "82°F",
                "activity": "high",
                "notes": "Noticed spotty brood pattern on 3 frames, possible varroa. Queen still laying on 6 frames. Super about half full.",
            },
            {
                "month": 9,
                "weather": "mild",
                "temp": "70°F",
                "activity": "moderate",
                "notes": "Brood down to 5 frames. Spotty pattern persists; possible causes include mites (uncapping cells) or weak queen. Removed super. Will perform mite test next inspection.",
                "action_items": [
                    {"description": "Perform mite test and assess queen", "priority": "medium", "timeframe_days": 7},
                ],
            },
            {
                "month": 10,
                "weather": "cool",
                "temp": "58°F",
                "activity": "low",
                "notes": "Alcohol wash: 13 mites per 300 bees (4%). Well above threshold; applied oxalic acid treatment. Population still decent despite mite pressure.",
                "action_items": [
                    {"description": "Monitor mite levels after treatment", "priority": "medium", "timeframe_days": 14},
                ],
            },
        ],
    },
]


def ensure_hive_and_inspections(db, user: User, hive_data: dict):
    hive = (
        db.query(Hive)
        .filter(Hive.nickname == hive_data["nickname"], Hive.user_id == user.id)
        .first()
    )
    if not hive:
        hive = Hive(
            nickname=hive_data["nickname"],
            location=hive_data["location"],
            description=hive_data["description"],
            user_id=user.id,
        )
        db.add(hive)
        db.flush()

    # Calculate relative dates: spread inspections over the past 8 months
    # This ensures inspections are in the past, within the 365-day window,
    # and include recent data for "last month" queries
    now = datetime.now()
    
    # Calculate how many inspections we have
    num_inspections = len(hive_data["inspections"])
    
    # Spread inspections over the past 8 months, with the most recent being ~2 weeks ago
    # This ensures "last month" queries will find data
    for i, inspection_data in enumerate(hive_data["inspections"]):
        # Reverse order: first inspection is oldest, last is most recent
        # Most recent inspection should be ~2 weeks ago (to be in "last month")
        # Oldest inspection should be ~8 months ago (still within 365-day window)
        days_ago = 14 + (num_inspections - 1 - i) * 30  # Spread over ~8 months
        inspection_dt = now - timedelta(days=days_ago)
        # Set time to 14:30 for consistency
        inspection_dt = inspection_dt.replace(hour=14, minute=30, second=0, microsecond=0)
        
        # Check if an inspection on that date already exists for this hive
        # Use a range check since exact timestamp might vary slightly
        existing = (
            db.query(Inspection)
            .filter(
                Inspection.hive_id == hive.id,
                Inspection.timestamp >= inspection_dt - timedelta(days=1),
                Inspection.timestamp <= inspection_dt + timedelta(days=1),
            )
            .first()
        )
        if existing:
            continue

        notes = inspection_data["notes"]
        queen_visible = "queen" in notes.lower() and ("spotted" in notes.lower() or "marked" in notes.lower() or "saw queen" in notes.lower())
        eggs_visible = "eggs" in notes.lower() or "laying" in notes.lower()
        larvae_visible = "larvae" in notes.lower()
        capped_brood_visible = "capped" in notes.lower() and "brood" in notes.lower()

        laying_pattern = None
        if "spotty" in notes.lower():
            laying_pattern = "patchy"
        elif eggs_visible:
            laying_pattern = "solid"

        insp = Inspection(
            hive_id=hive.id,
            timestamp=inspection_dt,
            inspection_date=inspection_dt.date(),
            notes=notes,
            weather=inspection_data.get("weather", ""),
            temperature=inspection_data.get("temp", ""),
            activity_level=inspection_data.get("activity", ""),
            queen_visible=queen_visible,
            eggs_visible=eggs_visible,
            larvae_visible=larvae_visible,
            capped_brood_visible=capped_brood_visible,
            laying_pattern=laying_pattern,
            action_items=inspection_data.get("action_items"),
        )
        db.add(insp)


def main():
    parser = argparse.ArgumentParser(description="Seed validation user with hives and inspections.")
    parser.add_argument("--email", required=True, help="User email to seed")
    parser.add_argument("--password", required=True, help="User password (used if creating)")
    parser.add_argument(
        "--reseed",
        action="store_true",
        help="Delete existing user and recreate with fresh data",
    )
    args = parser.parse_args()

    db = SessionLocal()

    try:
        user = ensure_user(db, args.email, args.password, reseed=args.reseed)
        for hive_data in HIVES_DATA:
            ensure_hive_and_inspections(db, user, hive_data)
        db.commit()
        print(f"✅ Seeded validation data for {args.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

