#!/usr/bin/env python3
"""
One-time script to analyze existing inspections and populate action items.

This script processes all existing inspections that don't have action items
and runs them through the LLM analyzer to populate the action_items field.
"""

import sys
import os
import logging
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
    """Get database URL from environment or use default."""
    return os.getenv('DATABASE_URL', 'sqlite:///./test.db')

def analyze_existing_inspections():
    """Analyze all existing inspections that don't have action items."""
    
    # Set up database connection
    database_url = get_database_url()
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Find all inspections without action items
        inspections_to_analyze = db.query(Inspection).filter(
            Inspection.action_items.is_(None)
        ).order_by(Inspection.timestamp.desc()).all()
        
        logger.info(f"Found {len(inspections_to_analyze)} inspections to analyze")
        
        if len(inspections_to_analyze) == 0:
            logger.info("No inspections need analysis - all are up to date!")
            return
        
        analyzed_count = 0
        action_items_found = 0
        
        for inspection in inspections_to_analyze:
            logger.info(f"Analyzing inspection ID {inspection.id} from {inspection.timestamp}")
            
            try:
                # Get the hive for context
                hive = db.query(Hive).filter(Hive.id == inspection.hive_id).first()
                if not hive:
                    logger.warning(f"Hive not found for inspection {inspection.id}")
                    continue
                
                # Analyze inspection notes and transcription
                analysis = analyze_inspection_for_actions(
                    inspection.notes or "",
                    inspection.transcription or ""
                )
                
                # Update inspection with action items
                if analysis.get("actions"):
                    inspection.action_items = analysis["actions"]
                    action_items_found += len(analysis["actions"])
                    
                    # Set action due date based on most urgent action
                    min_days = min(action.get("timeframe_days", 14) for action in analysis["actions"])
                    inspection.action_due_date = (datetime.now() + timedelta(days=min_days)).date()
                    
                    logger.info(f"  Found {len(analysis['actions'])} action items")
                    for action in analysis["actions"]:
                        logger.info(f"    - {action.get('description', 'Unknown')} (Priority: {action.get('priority', 'unknown')})")
                else:
                    # Set empty list to mark as analyzed
                    inspection.action_items = []
                    logger.info("  No action items found")
                
                # Update hive analysis timestamp
                hive.last_action_analysis = datetime.now()
                
                analyzed_count += 1
                
                # Commit every 10 inspections to avoid losing progress
                if analyzed_count % 10 == 0:
                    db.commit()
                    logger.info(f"Progress: analyzed {analyzed_count}/{len(inspections_to_analyze)} inspections")
                
            except Exception as e:
                logger.error(f"Failed to analyze inspection {inspection.id}: {e}")
                # Continue with other inspections
                continue
        
        # Final commit
        db.commit()
        
        logger.info(f"Analysis complete!")
        logger.info(f"  Inspections analyzed: {analyzed_count}")
        logger.info(f"  Total action items found: {action_items_found}")
        logger.info(f"  Average action items per inspection: {action_items_found/analyzed_count if analyzed_count > 0 else 0:.1f}")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def main():
    """Main function."""
    logger.info("Starting analysis of existing inspections...")
    
    try:
        analyze_existing_inspections()
        logger.info("Analysis completed successfully!")
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()