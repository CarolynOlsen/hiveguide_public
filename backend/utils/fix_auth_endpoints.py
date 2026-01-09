#!/usr/bin/env python3

import re
import sys

def fix_authentication_pattern():
    """Replace old vulnerable authentication with secure session validation"""
    
    with open('main.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern 1: Standard auth pattern
    old_pattern1 = re.compile(
        r'(\s+)session_id = request\.cookies\.get\("session_id"\)\s+'
        r'if not session_id:\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)\s+'
        r'db = SessionLocal\(\)\s+'
        r'user = db\.query\(User\)\.filter\(User\.id == int\(session_id\)\)\.first\(\)\s+'
        r'if not user:\s+'
        r'db\.close\(\)\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)',
        re.MULTILINE | re.DOTALL
    )
    
    replacement1 = r'\1user = require_auth(request)\n\1db = SessionLocal()'
    
    content = old_pattern1.sub(replacement1, content)
    
    # Pattern 2: Admin auth pattern (already fixed, but just in case)
    old_pattern2 = re.compile(
        r'(\s+)session_id = request\.cookies\.get\("session_id"\)\s+'
        r'if not session_id:\s+'
        r'raise HTTPException\(status_code=403, detail="Admin access required"\)\s+'
        r'db = SessionLocal\(\)\s+'
        r'admin_user = db\.query\(User\)\.filter\(User\.id == int\(session_id\)\)\.first\(\)\s+'
        r'if not admin_user or not admin_user\.is_admin:\s+'
        r'db\.close\(\)\s+'
        r'raise HTTPException\(status_code=403, detail="Admin access required"\)',
        re.MULTILINE | re.DOTALL
    )
    
    replacement2 = r'\1admin_user = require_auth(request)\n\1if not admin_user.is_admin:\n\1    raise HTTPException(status_code=403, detail="Admin access required")\n\1db = SessionLocal()'
    
    content = old_pattern2.sub(replacement2, content)
    
    # Pattern 3: Simple session_id usage without user lookup
    old_pattern3 = re.compile(
        r'(\s+)session_id = request\.cookies\.get\("session_id"\)\s+'
        r'if not session_id:\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)\s+'
        r'db = SessionLocal\(\)\s+'
        r'(try:\s+)?user_id = int\(session_id\)',
        re.MULTILINE | re.DOTALL
    )
    
    replacement3 = r'\1user = require_auth(request)\n\1db = SessionLocal()\n\1\2user_id = user.id'
    
    content = old_pattern3.sub(replacement3, content)
    
    # Pattern 4: Circle-specific auth patterns where user lookup happens later
    old_pattern4 = re.compile(
        r'(\s+)session_id = request\.cookies\.get\("session_id"\)\s+'
        r'if not session_id:\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)\s+'
        r'db = SessionLocal\(\)\s+'
        r'(current_user|user) = db\.query\(User\)\.filter\(User\.id == int\(session_id\)\)\.first\(\)\s+'
        r'if not \2:\s+'
        r'db\.close\(\)\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)',
        re.MULTILINE | re.DOTALL
    )
    
    replacement4 = r'\1\2 = require_auth(request)\n\1db = SessionLocal()'
    
    content = old_pattern4.sub(replacement4, content)
    
    # Pattern 5: Patterns where only session check is done
    old_pattern5 = re.compile(
        r'(\s+)session_id = request\.cookies\.get\("session_id"\)\s+'
        r'if not session_id:\s+'
        r'raise HTTPException\(status_code=401, detail="Authentication required"\)',
        re.MULTILINE
    )
    
    replacement5 = r'\1user = require_auth(request)'
    
    content = old_pattern5.sub(replacement5, content)
    
    with open('main.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Authentication patterns updated!")

if __name__ == "__main__":
    fix_authentication_pattern()