"""
User Hive Data Tool for RAG Chatbot

This tool allows the LangChain agent to query a user's personal hive and inspection
data from the PostgreSQL database, enabling personalized beekeeping advice.
"""

from langchain_core.tools import BaseTool
from langchain_core.callbacks import (
    CallbackManagerForToolRun,
    AsyncCallbackManagerForToolRun,
)
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

from backend.main import User, Hive, Inspection, SessionLocal
from .config import RAG_CONFIG


class UserHiveDataTool(BaseTool):
    """Tool to fetch comprehensive hive and inspection data for the authenticated user."""
    
    name: str = "get_user_hive_data"
    description: str = """Get the user's specific hive inspection data including exact weights, dates, and observations.
    
    USE THIS WHEN the user asks about:
    - "my hives", "my bees", "which of my hives", "when did I last see"
    - Personal inspection history, patterns, or trends
    - Comparing their own hives to each other
    - Questions about specific hive names, dates, or measurements from their records
    
    DO NOT USE for:
    - General beekeeping advice or best practices (use document search instead)
    - Questions asking "what should" or "how to" without personal context
    
    Parameters: 
    - hive_name (optional): Filter for specific hive by nickname
    - days_back (default 365): Days back to search (1-365)  
    - include_all_hives (default True): Whether to include all user's hives
    
    RETURNS: Formatted data with actual hive names, inspection dates, measurements, 
    queen status, brood observations, action items, and notes. Use this data to give 
    specific recommendations with exact hive names and dates."""
    
    user_id: int
    DEFAULT_DAYS_BACK: int = RAG_CONFIG.get('inspection_history_days', 365)
    
    def __init__(self, user_id: int):
        super().__init__(user_id=user_id)
        self._cached_default_output: Optional[str] = None
    
    def _run(
        self,
        hive_name: Optional[str] = None,
        days_back: int = DEFAULT_DAYS_BACK,
        include_all_hives: bool = True,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Fetch and format user's hive and inspection data."""
        
        # Input validation
        if days_back < 1:
            days_back = self.DEFAULT_DAYS_BACK
        if days_back > 365:
            days_back = 365  # Limit to 1 year max

        # Use cached default output when parameters match defaults
        if (
            hive_name in (None, "")
            and include_all_hives
            and days_back == self.DEFAULT_DAYS_BACK
            and self._cached_default_output is not None
        ):
            return self._cached_default_output
        
        db = SessionLocal()
        try:
            # Calculate the date threshold
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            # Get user's hives (including those from circles they're members of)
            user_hive_ids = self._get_accessible_hive_ids(db)
            
            if not user_hive_ids:
                return "No hives found for this user. To get started with HiveGuide, you'll need to create your first hive using the main application interface."
            
            # Filter by specific hive if requested
            hives_query = db.query(Hive).filter(Hive.id.in_(user_hive_ids))
            if hive_name and not include_all_hives:
                hives_query = hives_query.filter(Hive.nickname.ilike(f"%{hive_name}%"))
            
            hives = hives_query.all()
            
            if not hives:
                return f"No hives found matching '{hive_name}'. Your available hives are: {', '.join([h.nickname for h in db.query(Hive).filter(Hive.id.in_(user_hive_ids)).all()])}" if hive_name else "No hives found for this user."
            
            # Get recent inspections for these hives
            inspections = db.query(Inspection).filter(
                Inspection.hive_id.in_([h.id for h in hives]),
                Inspection.timestamp >= cutoff_date
            ).order_by(Inspection.timestamp.desc()).all()
            
            # Format the data for the LLM
            formatted_data = self._format_data_for_llm(hives, inspections, days_back)

            if (
                hive_name in (None, "")
                and include_all_hives
                and days_back == self.DEFAULT_DAYS_BACK
            ):
                self._cached_default_output = formatted_data

            return formatted_data
            
        except Exception as e:
            logging.error(f"Error fetching user hive data for user {self.user_id}: {e}")
            return f"I encountered an error retrieving your hive data. Please try again or contact support if the issue persists. (Error: {str(e)[:100]})"
        finally:
            db.close()

    async def _arun(
        self,
        hive_name: Optional[str] = None,
        days_back: int = DEFAULT_DAYS_BACK,
        include_all_hives: bool = True,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        return self._run(hive_name, days_back, include_all_hives)
    
    def _get_accessible_hive_ids(self, db: Session) -> list[int]:
        """Get IDs of hives the user owns or has access to through circles."""
        
        # Start with user's own hives
        own_hive_ids = [hive.id for hive in db.query(Hive).filter(Hive.user_id == self.user_id).all()]
        
        accessible_hive_ids = own_hive_ids[:]
        
        # Try to get circle hive IDs, gracefully handle if Circle tables don't exist
        try:
            from backend.main import Circle, CircleMembership
            circle_hives = db.query(Hive).join(
                Circle, Hive.user_id == Circle.owner_id
            ).join(
                CircleMembership, Circle.id == CircleMembership.circle_id
            ).filter(
                CircleMembership.user_id == self.user_id,
                Hive.user_id != self.user_id  # Exclude own hives to avoid duplicates
            ).all()
            accessible_hive_ids.extend([hive.id for hive in circle_hives])
        except Exception as e:
            logging.warning(f"Could not fetch circle hive access: {e}")
            # Continue with just own hives
        
        return accessible_hive_ids
    
    def _format_data_for_llm(self, hives: list[Hive], inspections: list[Inspection], days_back: int) -> str:
        """Format hive and inspection data in a comprehensive way for LLM analysis."""
        
        lines = []
        lines.append(f"=== USER'S HIVE DATA (Last {days_back} days) ===")
        lines.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Group inspections by hive
        inspections_by_hive = {}
        for inspection in inspections:
            if inspection.hive_id not in inspections_by_hive:
                inspections_by_hive[inspection.hive_id] = []
            inspections_by_hive[inspection.hive_id].append(inspection)
        
        # Format each hive and its inspections
        for hive in hives:
            lines.append(f"🏠 HIVE: {hive.nickname}")
            lines.append(f"   Location: {hive.location or 'Not specified'}")
            lines.append(f"   Description: {hive.description or 'No description'}")
            
            hive_inspections = inspections_by_hive.get(hive.id, [])
            lines.append(f"   Recent Inspections: {len(hive_inspections)} in last {days_back} days")
            
            if hive_inspections:
                lines.append("")
                for i, inspection in enumerate(hive_inspections, 1):
                    lines.append(f"   📋 INSPECTION #{i} - {inspection.timestamp.strftime('%Y-%m-%d %H:%M')}")
                    lines.append(f"      Weather: {inspection.weather or 'Not recorded'}")
                    lines.append(f"      Temperature: {inspection.temperature or 'Not recorded'}")
                    lines.append("")
                    
                    # Brood and Queen Status
                    lines.append("      🐝 COLONY STATUS:")
                    lines.append(f"         Queen visible: {'✓' if inspection.queen_visible else '✗'}")
                    lines.append(f"         Eggs visible: {'✓' if inspection.eggs_visible else '✗'}")
                    lines.append(f"         Larvae visible: {'✓' if inspection.larvae_visible else '✗'}")
                    lines.append(f"         Capped brood visible: {'✓' if inspection.capped_brood_visible else '✗'}")
                    lines.append(f"         Laying pattern: {inspection.laying_pattern or 'Not recorded'}")
                    lines.append(f"         Activity level: {inspection.activity_level or 'Not recorded'}")
                    lines.append("")
                    
                    # Media and Documentation
                    photo_count = len(inspection.photos) if inspection.photos else 0
                    lines.append(f"      📷 Documentation: {photo_count} photos")
                    
                    if inspection.notes:
                        lines.append(f"      📝 Notes: {inspection.notes}")
                    
                    if inspection.transcription:
                        lines.append(f"      🎤 Voice Notes: {inspection.transcription}")
                    
                    # Action Items
                    if inspection.action_items:
                        lines.append("      ⚠️ Action Items:")
                        for action in inspection.action_items:
                            priority = action.get('priority', 'unknown')
                            desc = action.get('description', 'Unknown action')
                            lines.append(f"         - {desc} (Priority: {priority})")
                    
                    lines.append("")
            else:
                lines.append("   No recent inspections found.")
            
            lines.append("-" * 60)
            lines.append("")
        
        # Summary statistics
        total_inspections = len(inspections)
        unique_hives_inspected = len(set(i.hive_id for i in inspections))
        
        lines.append(f"📊 SUMMARY:")
        lines.append(f"   Total hives: {len(hives)}")
        lines.append(f"   Hives with recent inspections: {unique_hives_inspected}")
        lines.append(f"   Total inspections in period: {total_inspections}")
        
        if inspections:
            avg_inspections_per_hive = total_inspections / len(hives)
            most_recent = max(inspections, key=lambda x: x.timestamp)
            lines.append(f"   Average inspections per hive: {avg_inspections_per_hive:.1f}")
            lines.append(f"   Most recent inspection: {most_recent.timestamp.strftime('%Y-%m-%d')} ({most_recent.hive.nickname})")
        
        return "\n".join(lines)

    def invalidate_cache(self) -> None:
        self._cached_default_output = None

    refresh = invalidate_cache