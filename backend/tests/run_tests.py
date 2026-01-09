#!/usr/bin/env python3
"""
Test runner script for HiveScribe
"""
import subprocess
import sys
import os


def run_command(command, description):
    """Run a command and handle errors"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} passed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(e.stdout)
        print(e.stderr)
        return False


def main():
    """Run all tests and checks"""
    print("🐝 Running HiveScribe test suite...")
    
    # Set test database URL if not already set
    if not os.environ.get("DATABASE_URL"):
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        print("🔧 Set DATABASE_URL to in-memory SQLite for testing")
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Warning: Not in a virtual environment")
    
    # Install dev dependencies
    print("📦 Installing development dependencies...")
    if not run_command(f"{sys.executable} -m pip install -r requirements-dev.txt -q", "Installing dev dependencies"):
        return False
    
    # Basic syntax check
    if not run_command(f"{sys.executable} -m py_compile main.py", "Python syntax check"):
        return False
    
    # Run tests
    if not run_command(
        f"{sys.executable} -m pytest tests/test_main.py -v --tb=short",
        "Unit tests"
    ):
        return False
    
    # Run with coverage
    print("📊 Running tests with coverage...")
    if not run_command(
        f"{sys.executable} -m pytest tests/test_main.py --cov=main --cov-report=term-missing",
        "Coverage report"
    ):
        return False
    
    print("✅ All tests passed!")
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 