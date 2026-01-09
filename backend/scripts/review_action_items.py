#!/usr/bin/env python3
"""
Script to review all inspections and their extracted action items.
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import Inspection, Hive

def get_database_url():
    """Get database URL from environment or use default."""
    return os.getenv('DATABASE_URL', 'sqlite:///./test.db')

def review_action_items():
    """Review all inspections and their action items."""
    
    # Set up database connection
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Get all inspections with action items, ordered by timestamp
        inspections = db.query(Inspection).filter(
            Inspection.action_items.isnot(None)
        ).order_by(Inspection.timestamp.desc()).all()
        
        print(f"=== REVIEW OF ACTION ITEMS FROM {len(inspections)} INSPECTIONS ===\n")
        
        for i, inspection in enumerate(inspections, 1):
            # Get hive info
            hive = db.query(Hive).filter(Hive.id == inspection.hive_id).first()
            hive_name = hive.nickname if hive else f"Hive {inspection.hive_id}"
            hive_location = hive.location if hive and hive.location else "Unknown Location"
            
            print(f"📋 INSPECTION #{i}")
            print(f"🏠 Hive: {hive_name} ({hive_location})")
            print(f"📅 Date: {inspection.timestamp.strftime('%Y-%m-%d %H:%M')}")
            print(f"🔗 ID: {inspection.id}")
            
            # Show original notes/transcription
            print(f"\n📝 ORIGINAL NOTES:")
            if inspection.notes:
                print(f"   Notes: {inspection.notes[:200]}{'...' if len(inspection.notes) > 200 else ''}")
            if inspection.transcription:
                print(f"   Transcription: {inspection.transcription[:200]}{'...' if len(inspection.transcription) > 200 else ''}")
            
            if not inspection.notes and not inspection.transcription:
                print("   (No notes or transcription)")
            
            # Show extracted action items
            action_items = inspection.action_items if inspection.action_items else []
            
            print(f"\n🎯 EXTRACTED ACTION ITEMS ({len(action_items)}):")
            if action_items:
                for j, action in enumerate(action_items, 1):
                    priority = action.get('priority', 'unknown')
                    description = action.get('description', 'No description')
                    timeframe = action.get('timeframe_days', 'N/A')
                    category = action.get('category', 'other')
                    
                    # Priority emoji
                    priority_emoji = {
                        'urgent': '🔴',
                        'high': '🟠', 
                        'medium': '🟡',
                        'low': '🟢'
                    }.get(priority, '⚪')
                    
                    print(f"   {j}. {priority_emoji} {description}")
                    print(f"      Priority: {priority} | Timeframe: {timeframe} days | Category: {category}")
            else:
                print("   (No action items extracted)")
            
            # Show due date if set
            if inspection.action_due_date:
                print(f"\n📅 Action Due Date: {inspection.action_due_date}")
            
            print(f"\n{'='*80}\n")
        
        # Summary statistics
        total_actions = sum(len(insp.action_items) if insp.action_items else 0 for insp in inspections)
        inspections_with_actions = sum(1 for insp in inspections if insp.action_items and len(insp.action_items) > 0)
        
        print(f"📊 SUMMARY:")
        print(f"   Total Inspections Analyzed: {len(inspections)}")
        print(f"   Inspections with Action Items: {inspections_with_actions}")
        print(f"   Total Action Items Extracted: {total_actions}")
        print(f"   Average Actions per Inspection: {total_actions/len(inspections):.1f}")
        
        # Priority breakdown
        priority_counts = {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0, 'unknown': 0}
        for insp in inspections:
            if insp.action_items:
                for action in insp.action_items:
                    priority = action.get('priority', 'unknown')
                    priority_counts[priority] = priority_counts.get(priority, 0) + 1
        
        print(f"\n📈 PRIORITY BREAKDOWN:")
        for priority, count in priority_counts.items():
            if count > 0:
                emoji = {'urgent': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢', 'unknown': '⚪'}[priority]
                print(f"   {emoji} {priority.title()}: {count}")
        
    finally:
        db.close()

if __name__ == "__main__":
    review_action_items()