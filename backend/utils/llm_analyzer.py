"""
LLM Action Item Analyzer for Beehive Inspection Notes

This module uses OpenRouter API with GPT-OSS 20B to extract actionable items
from inspection notes and transcriptions.
"""

import os
import json
import logging
import yaml
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional
import openai
import requests

logger = logging.getLogger(__name__)

def _is_winter_month(inspection_date: Optional[date]) -> bool:
    """Check if the given date falls in winter months (Nov-Feb)."""
    if not inspection_date:
        return False
    winter_months = [11, 12, 1, 2]  # Nov, Dec, Jan, Feb
    return inspection_date.month in winter_months

def _load_config():
    """Load configuration from config.yaml if present."""
    config = {}
    try:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
    except Exception as e:
        logger.warning(f"Could not load config.yaml: {e}")
    return config

class ActionItemAnalyzer:
    """Analyzes inspection notes to extract actionable items using LLM."""
    
    def __init__(self):
        # Load config from config.yaml
        config = _load_config()
        
        # Use OpenRouter API with GPT-OSS 20B model
        # Check environment first, then config.yaml
        self.api_key = os.getenv('OPENROUTER_API_KEY') or config.get('openrouter_api_key')
        self.model = "openai/gpt-oss-20b"
        self.base_url = "https://openrouter.ai/api/v1"
        
        # Fallback to OpenAI if OpenRouter not available
        if not self.api_key:
            self.api_key = os.getenv('OPENAI_API_KEY') or config.get('openai_api_key')
            self.model = "gpt-3.5-turbo"
            self.base_url = "https://api.openai.com/v1"
            if self.api_key:
                logger.warning("OpenRouter API key not found, falling back to OpenAI")
    
    def analyze_inspection_notes(self, notes: str, transcription: str = "", inspection_date: Optional[date] = None) -> Dict:
        """
        Analyze inspection notes and transcription to extract action items.
        
        Args:
            notes: Inspection notes text
            transcription: Audio transcription text
            inspection_date: Optional inspection date to filter seasonal suggestions
            
        Returns:
            Dict with action items and metadata
        """
        if not self.api_key:
            logger.error("No API key available for LLM analysis")
            return self._fallback_analysis(notes, transcription, inspection_date)
        
        # Combine notes and transcription
        combined_text = f"{transcription}\n\n{notes}".strip()
        
        if not combined_text:
            return {"actions": [], "analysis_type": "empty"}
        
        # Retry logic for JSON parsing failures
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Use OpenRouter/OpenAI API
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        **({"HTTP-Referer": "https://hive-dashboard.app"} if "openrouter" in self.base_url else {})
                    },
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": self._get_system_prompt()
                            },
                            {
                                "role": "user",
                                "content": f"Analyze these inspection notes and extract action items:\n\n{combined_text}"
                            }
                        ],
                        "temperature": 0.1,
                        "max_tokens": 500
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    
                    try:
                        # Parse JSON response
                        parsed = json.loads(content)
                        parsed["analysis_type"] = "llm"
                        parsed["model_used"] = self.model
                        return parsed
                    except json.JSONDecodeError:
                        logger.error(f"Attempt {attempt + 1}: Failed to parse LLM response: {content[:200]}...")
                        if attempt == max_retries - 1:
                            # Last attempt failed, fall back
                            return self._fallback_analysis(notes, transcription)
                        # Continue to next retry
                        continue
                else:
                    logger.error(f"LLM API error: {response.status_code} - {response.text}")
                    return self._fallback_analysis(notes, transcription)
                    
            except Exception as e:
                logger.error(f"Attempt {attempt + 1}: LLM request failed: {e}")
                if attempt == max_retries - 1:
                    return self._fallback_analysis(notes, transcription)
                continue
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for action item extraction."""
        return """You are a beekeeping assistant. Analyze inspection notes and extract specific, actionable items that the beekeeper needs to do.

CRITICAL RULES:
- Only extract actions explicitly mentioned or clearly implied in the notes
- Do NOT make up specific details (dosages, treatment schedules, etc.) if not stated
- Keep descriptions concise (under 8 words when possible)
- Consolidate similar actions (combine multiple feeding actions into one)
- Ignore past/completed events - only extract future actions needed
- Pay attention to negative statements ("no queen cells found" = don't suggest checking queen cells)
- Comments about comb building progress do NOT need action items
- If no specific actions and colony is alive, suggest "Normal inspection" in 7-14 days (May-October)

QUEEN CELL STAGES:
- Queen cups: Empty wax structures, no action needed
- Queen cells (wet/filled): Contains egg/larva + royal jelly = "Swarm risk? [exact terminology] mentioned"
- Capped queen cells (if not removed): Queen developing inside = "Check for new laying queen" in 14 days
- For ambiguous mentions, use beekeeper's exact terminology in "Swarm risk? [their words] mentioned"

Focus on:
- Equipment needs (feeders, supers, frames, etc.)
- Health concerns (queen issues, disease treatment, pest management)
- Maintenance tasks (replacing equipment, adding boxes)
- Follow-up actions with timeframes
- Harvest activities
- Normal inspections when no other actions specified

CRITICAL: You MUST respond with ONLY a valid JSON object. No other text before or after.

Use this EXACT JSON schema:
{
  "actions": [
    {
      "description": "Clear, concise action to take",
      "priority": "low|medium|high|urgent", 
      "timeframe_days": 7
    }
  ]
}

EXAMPLES of valid JSON responses:
{"actions": [{"description": "Check for new laying queen", "priority": "high", "timeframe_days": 14}]}
{"actions": [{"description": "Swarm risk? Queen cells mentioned", "priority": "high", "timeframe_days": 3}]}
{"actions": [{"description": "Normal inspection", "priority": "medium", "timeframe_days": 7}]}
{"actions": []}

Priority guidelines:
- urgent: Active swarming in progress, immediate danger
- high: Health concerns, missing queen, disease treatment
- medium: Equipment needs, feeding, routine maintenance, normal inspections
- low: General improvements, non-critical tasks

Timeframe guidelines:
- 1-3 days: Urgent health issues
- 7 days: Equipment needs, routine checks
- 14 days: General maintenance, checking for new queens after queen cells
- 30 days: Seasonal preparations

Examples of good concise descriptions:
- "Remove Apiguard" not "Schedule and apply the next dose"
- "Swap wooden super" not "Swap the current wood super onto the hive..."
- "Consider feeding" not "Refill the frame feeder with appropriate feed..."
- "Swarm risk? Queen cells mentioned" (when queen cells found but not specified as capped)
- "Check for new laying queen" (14 days after capped queen cells seen that weren't removed)
- "Normal inspection" (when no other actions and colony alive)
"""

    def _fallback_analysis(self, notes: str, transcription: str, inspection_date: Optional[date] = None) -> Dict:
        """
        Rule-based fallback analysis when LLM is unavailable.
        
        Args:
            notes: Inspection notes
            transcription: Audio transcription
            inspection_date: Optional inspection date to filter seasonal suggestions
            
        Returns:
            Dict with extracted action items
        """
        combined_text = f"{transcription}\n\n{notes}".strip().lower()
        actions = []
        
        # Rule-based action detection - very basic patterns only as fallback
        action_patterns = [
            # Equipment patterns - only explicit mentions
            (r'add.*super', "Add super", "medium", 7),
            (r'add.*deep', "Add deep", "medium", 7),
            
            # Harvest patterns - explicit mentions only
            (r'take.*capped', "Take capped frames", "medium", 7),
            
            # Feeding - consolidate various feeding mentions
            (r'feed|refill.*feeder|top.*feeder', "Consider feeding", "medium", 7),
        ]
        
        import re
        
        # Simple rule-based patterns for basic equipment/feeding only
        for pattern, description, priority, timeframe in action_patterns:
            if re.search(pattern, combined_text):
                actions.append({
                    "description": description,
                    "priority": priority,
                    "timeframe_days": timeframe
                })
        
        # Look for "next steps" mentions
        if "next step" in combined_text:
            # Try to extract the next steps section
            lines = combined_text.split('\n')
            for i, line in enumerate(lines):
                if "next step" in line.lower():
                    # Take the next few lines as action items
                    for j in range(i, min(i+3, len(lines))):
                        if lines[j].strip() and "next step" not in lines[j].lower():
                            actions.append({
                                "description": lines[j].strip().capitalize(),
                                "priority": "medium",
                                "timeframe_days": 7
                            })
        
        # Add default normal inspection if no other actions and colony seems alive
        # BUT skip during winter months (Nov-Feb)
        if not actions and not any(doom_word in combined_text for doom_word in ["doom", "dead", "shook out", "took their hive away"]):
            if not _is_winter_month(inspection_date):
                actions.append({
                    "description": "Normal inspection",
                    "priority": "medium",
                    "timeframe_days": 10  # 7-14 days average
                })
        
        return {
            "actions": actions,
            "analysis_type": "rule_based"
        }

    def calculate_urgency_score(self, hive_data: Dict) -> tuple[str, int]:
        """
        Calculate urgency color and score for a hive.
        
        Args:
            hive_data: Dict containing hive info, last inspection, and action items
            
        Returns:
            Tuple of (color, urgency_score) where color is "red|yellow|green"
        """
        now = datetime.now()
        urgency_score = 0
        
        # Check inspection recency
        last_inspection = hive_data.get('last_inspection_date')
        if last_inspection:
            days_since = (now.date() - last_inspection).days
            if days_since > 14:  # Overdue inspection
                urgency_score += 10
            elif days_since > 10:
                urgency_score += 5
        else:
            urgency_score += 15  # Never inspected
        
        # Check action items
        action_items = hive_data.get('action_items', [])
        for action in action_items:
            priority = action.get('priority', 'low')
            if priority == 'urgent':
                urgency_score += 15
            elif priority == 'high':
                urgency_score += 10
            elif priority == 'medium':
                urgency_score += 5
            elif priority == 'low':
                urgency_score += 2
        
        # Determine color
        if urgency_score >= 15:
            return ("red", urgency_score)
        elif urgency_score >= 5:
            return ("yellow", urgency_score)
        else:
            return ("green", urgency_score)


# Global instance
analyzer = ActionItemAnalyzer()


def analyze_inspection_for_actions(notes: str, transcription: str = "", inspection_date: Optional[date] = None) -> Dict:
    """
    Convenience function to analyze inspection notes.
    
    Args:
        notes: Inspection notes
        transcription: Audio transcription
        inspection_date: Optional inspection date to filter seasonal suggestions
        
    Returns:
        Analysis results with action items
    """
    result = analyzer.analyze_inspection_notes(notes, transcription, inspection_date)
    
    # Filter out "Normal inspection" suggestions during winter months (Nov-Feb)
    if result.get("actions") and _is_winter_month(inspection_date):
        result["actions"] = [
            action for action in result["actions"]
            if action.get("description", "").lower() != "normal inspection"
        ]
    
    return result


def get_hive_urgency(hive_data: Dict) -> tuple[str, int]:
    """
    Convenience function to get hive urgency.
    
    Args:
        hive_data: Hive data dictionary
        
    Returns:
        Tuple of (color, urgency_score)
    """
    return analyzer.calculate_urgency_score(hive_data)