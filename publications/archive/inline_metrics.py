#!/usr/bin/env python3
"""
Inline metrics from metrics.tex into aaai_paper.tex
AAAI requires a single .tex file - no \input commands allowed.
"""
import re
from pathlib import Path

PAPER_FILE = Path(__file__).parent / "aaai_paper.tex"
METRICS_FILE = Path(__file__).parent / "metrics.tex"

def inline_metrics():
    """Replace the metrics section in the paper with inlined content from metrics.tex."""
    # Read metrics content
    if not METRICS_FILE.exists():
        print(f"Warning: {METRICS_FILE} not found. Run generate_metrics_tex.py first.")
        return False
    
    with open(METRICS_FILE, 'r') as f:
        metrics_content = f.read()
    
    # Read paper
    with open(PAPER_FILE, 'r') as f:
        paper_content = f.read()
    
    # Find the metrics section - look for the comment marker
    # Pattern matches from "% Auto-generated metrics" through all the commands until the next major section
    pattern = r'(% Auto-generated metrics from validation results.*?)(?=\n% For submission|\n\\author|\n\\setcounter|\n\\begin\{document\})'
    
    # Create replacement with proper header
    header = """% Auto-generated metrics from validation results
% NOTE: Inlined from metrics.tex - \\input command is not allowed per AAAI requirements
% DO NOT EDIT MANUALLY - regenerate with: python generate_metrics_tex.py && python inline_metrics.py

"""
    replacement = header + metrics_content
    
    # Replace - need to escape backslashes in replacement for regex
    def replacer(match):
        return replacement
    
    new_content = re.sub(pattern, replacer, paper_content, flags=re.DOTALL)
    
    if new_content == paper_content:
        print("Warning: Could not find metrics section to replace (metrics may already be inlined)")
        # This is not a fatal error - metrics might already be inlined
        return True  # Return True so script doesn't fail
    
    # Write back
    with open(PAPER_FILE, 'w') as f:
        f.write(new_content)
    
    print(f"✓ Inlined metrics into {PAPER_FILE.name}")
    return True

if __name__ == "__main__":
    inline_metrics()

