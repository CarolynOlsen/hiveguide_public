#!/usr/bin/env python3
"""
Re-analyze all existing inspections with the improved system and UPDATE the database.

This script will overwrite existing action items with the new, improved analysis.
"""

import sys
import os
import logging
import yaml
from datetime import datetime, timedelta

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.main import Inspection, Hive
from backend.utils.llm_analyzer import analyze_inspection_for_actions

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment or config.yaml."""
    # Check environment variable first
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return database_url
    
    # Try to load from config.yaml
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config and config.get('database_url'):
                    return config['database_url']
    except Exception as e:
        logger.warning(f"Could not load config.yaml: {e}")
    
    # Fallback to default
    return 'sqlite:///./test.db'

def reanalyze_and_update_all_inspections():
    """Re-analyze all inspections with improved system and UPDATE the database."""
    
    # Set up database connection
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Get all inspections, ordered by timestamp
        all_inspections = db.query(Inspection).order_by(Inspection.timestamp.desc()).all()
        
        logger.info(f"Re-analyzing and updating {len(all_inspections)} inspections with improved system")
        
        if len(all_inspections) == 0:
            logger.info("No inspections found!")
            return
        
        updated_count = 0
        action_items_found = 0
        
        for inspection in all_inspections:
            # Get the hive for context
            hive = db.query(Hive).filter(Hive.id == inspection.hive_id).first()
            if not hive:
                logger.warning(f"Hive not found for inspection {inspection.id}")
                continue
            
            hive_name = hive.nickname if hive else f"Hive {inspection.hive_id}"
            
            logger.info(f"Re-analyzing inspection {inspection.id} for {hive_name} from {inspection.timestamp.strftime('%Y-%m-%d')}")
            
            try:
                # Analyze with improved system
                # Pass inspection_date to filter seasonal suggestions
                inspection_date_for_analysis = getattr(inspection, 'inspection_date', None)
                analysis = analyze_inspection_for_actions(
                    inspection.notes or "",
                    inspection.transcription or "",
                    inspection_date=inspection_date_for_analysis
                )
                
                # Update inspection with new action items
                new_actions = analysis.get("actions", [])
                inspection.action_items = new_actions
                
                # Set action due date based on most urgent action, anchored to inspection date
                if new_actions:
                    min_days = min(action.get("timeframe_days", 14) for action in new_actions)
                    # Use inspection_date if available, otherwise fallback to timestamp
                    base_date = getattr(inspection, 'inspection_date', None) or inspection.timestamp.date()
                    inspection.action_due_date = (base_date + timedelta(days=min_days))
                    action_items_found += len(new_actions)
                    logger.info(f"  Updated with {len(new_actions)} action items")
                    for action in new_actions:
                        logger.info(f"    - {action.get('description', 'Unknown')} (Priority: {action.get('priority', 'unknown')})")
                else:
                    # Clear action due date if no actions
                    inspection.action_due_date = None
                    logger.info(f"  No action items found")
                
                # Update hive analysis timestamp
                hive.last_action_analysis = datetime.now()
                
                updated_count += 1
                
                # Commit every 5 inspections to avoid losing progress
                if updated_count % 5 == 0:
                    db.commit()
                    logger.info(f"Progress: updated {updated_count}/{len(all_inspections)} inspections")
                
            except Exception as e:
                logger.error(f"Failed to re-analyze inspection {inspection.id}: {e}")
                # Continue with other inspections
                continue
        
        # Final commit
        db.commit()
        
        logger.info(f"✅ RE-ANALYSIS AND UPDATE COMPLETE!")
        logger.info(f"   Inspections Updated: {updated_count}")
        logger.info(f"   Total Action Items Found: {action_items_found}")
        logger.info(f"   Average Actions per Inspection: {action_items_found/updated_count if updated_count > 0 else 0:.1f}")
        
        # Summary of action types
        all_updated_inspections = db.query(Inspection).filter(
            Inspection.action_items.isnot(None)
        ).all()
        
        priority_counts = {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0}
        for insp in all_updated_inspections:
            if insp.action_items:
                for action in insp.action_items:
                    priority = action.get('priority', 'unknown')
                    if priority in priority_counts:
                        priority_counts[priority] += 1
        
        logger.info(f"📊 FINAL PRIORITY BREAKDOWN:")
        for priority, count in priority_counts.items():
            if count > 0:
                emoji = {'urgent': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '🟢'}[priority]
                logger.info(f"   {emoji} {priority.title()}: {count}")
        
    except Exception as e:
        logger.error(f"Re-analysis failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """Main function."""
    logger.info("🔄 Starting re-analysis and update of all existing inspections...")
    logger.info("⚠️  This will OVERWRITE existing action items with improved analysis")
    
    try:
        reanalyze_and_update_all_inspections()
        logger.info("🎉 Re-analysis and update completed successfully!")
    except Exception as e:
        logger.error(f"❌ Re-analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()