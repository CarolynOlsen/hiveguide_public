#!/bin/bash

# Security Verification Script for HiveGuide
# Run this before making the repository public

set -e

echo "🔒 HiveGuide Security Verification"
echo "===================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ISSUES_FOUND=0

# Check 1: Verify config.yaml is not tracked
echo -e "${BLUE}[1/7] Checking if config.yaml is tracked in git...${NC}"
if git ls-files | grep -q "^config.yaml$"; then
    echo -e "${RED}❌ FAIL: config.yaml is tracked in git!${NC}"
    echo "   Run: git rm --cached config.yaml"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: config.yaml is not tracked${NC}"
fi
echo ""

# Check 2: Verify no .env files are tracked (except .env.example and .env.production)
echo -e "${BLUE}[2/7] Checking for tracked .env files...${NC}"
TRACKED_ENV=$(git ls-files | grep "\.env" | grep -v "\.env\.example" | grep -v "\.env\.production" | grep -v "\.xcode\.env$" || true)
if [ -n "$TRACKED_ENV" ]; then
    echo -e "${RED}❌ FAIL: Unexpected .env files are tracked:${NC}"
    echo "$TRACKED_ENV"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: No unexpected .env files tracked${NC}"
fi
echo ""

# Check 3: Search for potential passwords in tracked files
echo -e "${BLUE}[3/7] Searching for potential passwords in code...${NC}"
if git grep -i "password.*=.*['\"]" -- "*.py" "*.ts" "*.tsx" "*.js" "*.jsx" "*.sh" | grep -v "password_hash" | grep -v "APP_PASSWORD" | grep -v "APPLE_ID" | grep -v "your-" | grep -v "example" | grep -v "placeholder" | grep -v "type.*password" | grep -v "input.*password" | grep -v "Password:" | grep -v "password:" | grep -v "# password" | grep -v "// password" | grep -v "add_argument" | grep -v "test_password.*=.*['\"]test" > /tmp/password_check.txt 2>/dev/null; then
    echo -e "${YELLOW}⚠️  WARNING: Found potential password assignments:${NC}"
    head -10 /tmp/password_check.txt
    echo "   Please review these manually"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: No obvious password assignments found${NC}"
fi
echo ""

# Check 4: Search for API keys
echo -e "${BLUE}[4/7] Searching for potential API keys...${NC}"
if git grep -E "(sk-[a-zA-Z0-9]{32,}|AIza[a-zA-Z0-9_-]{35})" -- "*.py" "*.ts" "*.tsx" "*.js" "*.jsx" "*.sh" "*.yaml" "*.yml" > /tmp/apikey_check.txt 2>/dev/null; then
    echo -e "${RED}❌ FAIL: Found potential API keys:${NC}"
    cat /tmp/apikey_check.txt
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: No API keys found in code${NC}"
fi
echo ""

# Check 5: Check for email addresses (excluding examples)
echo -e "${BLUE}[5/7] Searching for email addresses...${NC}"
if git grep -E "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" -- "*.py" "*.ts" "*.tsx" "*.js" "*.jsx" "*.sh" | grep -v "example.com" | grep -v "your-" | grep -v "@gmail.com" | grep -v "email@" | grep -v "user@" | grep -v "test@" | grep -v "// " | grep -v "# " > /tmp/email_check.txt 2>/dev/null; then
    echo -e "${YELLOW}⚠️  WARNING: Found email addresses:${NC}"
    cat /tmp/email_check.txt
    echo "   Please review these manually"
else
    echo -e "${GREEN}✅ PASS: No personal email addresses found${NC}"
fi
echo ""

# Check 6: Verify critical files exist
echo -e "${BLUE}[6/7] Verifying security documentation exists...${NC}"
if [ ! -f "config.yaml.example" ]; then
    echo -e "${RED}❌ FAIL: config.yaml.example not found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
elif [ ! -f "SECURITY_CHECKLIST.md" ]; then
    echo -e "${RED}❌ FAIL: SECURITY_CHECKLIST.md not found${NC}"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: Security documentation exists${NC}"
fi
echo ""

# Check 7: Verify add_admin_user.py is deleted
echo -e "${BLUE}[7/7] Verifying hardcoded credentials file is deleted...${NC}"
if [ -f "backend/rag/utils/add_admin_user.py" ]; then
    echo -e "${RED}❌ FAIL: add_admin_user.py still exists!${NC}"
    echo "   Run: rm backend/rag/utils/add_admin_user.py"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
elif git ls-files | grep -q "add_admin_user.py"; then
    echo -e "${RED}❌ FAIL: add_admin_user.py is still tracked in git!${NC}"
    echo "   Run: git rm backend/rag/utils/add_admin_user.py"
    ISSUES_FOUND=$((ISSUES_FOUND + 1))
else
    echo -e "${GREEN}✅ PASS: Hardcoded credentials file removed${NC}"
fi
echo ""

# Summary
echo "===================================="
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed! Repository is ready to be made public.${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  IMPORTANT: Before going public, remember to:${NC}"
    echo "1. Rotate your Railway database credentials"
    echo "2. Review SECURITY_CHECKLIST.md for additional steps"
    echo "3. Run: git log -p | grep -i 'password\\|api_key' to check history"
    exit 0
else
    echo -e "${RED}❌ Found $ISSUES_FOUND issue(s). Please fix before making public.${NC}"
    echo ""
    echo "Review the issues above and consult SECURITY_CHECKLIST.md"
    exit 1
fi
