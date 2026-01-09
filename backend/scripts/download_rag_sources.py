#!/usr/bin/env python3
"""
Download RAG source PDFs from configured URLs.
Dynamically reads from backend/rag/config.py to ensure sync.
"""

import sys
from pathlib import Path
import subprocess
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.config import PDF_SOURCES, ensure_sources_directory

def validate_pdf(file_path: Path) -> bool:
    """
    Validate that the downloaded file is a valid PDF.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if valid PDF, False otherwise
    """
    if not file_path.exists():
        return False
    
    # Check file size (must be > 1KB to be valid)
    if file_path.stat().st_size < 1024:
        print(f"   ⚠️  File too small ({file_path.stat().st_size} bytes) - likely corrupted")
        return False
    
    # Check PDF magic bytes (PDFs start with %PDF-)
    try:
        with open(file_path, 'rb') as f:
            header = f.read(5)
            if header != b'%PDF-':
                print(f"   ⚠️  Invalid PDF header - file may be corrupted")
                return False
    except Exception as e:
        print(f"   ⚠️  Could not read file: {e}")
        return False
    
    return True

def download_pdf(url: str, output_path: Path, timeout: int = 60) -> bool:
    """
    Download a PDF from the given URL using curl.
    
    Args:
        url: The URL to download from
        output_path: Path where the PDF should be saved
        timeout: Download timeout in seconds
        
    Returns:
        True if download was successful and valid, False otherwise
    """
    try:
        print(f"   Downloading from: {url}")
        
        # Use curl with proper error handling
        result = subprocess.run(
            [
                'curl', '-L',  # Follow redirects
                '-o', str(output_path),
                '--fail',  # Fail on HTTP errors
                '--silent',  # Silent mode
                '--show-error',  # Show errors
                '--max-time', str(timeout),  # Timeout
                '--user-agent', 'Mozilla/5.0 (compatible; HiveGuide/1.0)',  # User agent
                url
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print(f"   ❌ Download failed: {result.stderr.strip()}")
            # Clean up failed download
            if output_path.exists():
                output_path.unlink()
            return False
        
        # Validate the downloaded file
        if not validate_pdf(output_path):
            print(f"   ❌ Downloaded file is not a valid PDF")
            output_path.unlink()
            return False
        
        file_size = output_path.stat().st_size
        print(f"   ✅ Downloaded successfully ({file_size:,} bytes)")
        return True
        
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        if output_path.exists():
            output_path.unlink()
        return False

def download_all_sources():
    """Download all PDF sources configured in PDF_SOURCES."""
    print("🐝 RAG Source PDF Download Script")
    print("=" * 60)
    
    # Ensure sources directory exists
    sources_dir = ensure_sources_directory()
    print(f"📁 Sources directory: {sources_dir}")
    print()
    
    # Get active sources from config
    active_sources = {k: v for k, v in PDF_SOURCES.items() if k and not k.startswith('#')}
    total = len(active_sources)
    
    print(f"📚 Found {total} active source(s) in config.py")
    print()
    
    successful = 0
    failed = 0
    skipped = 0
    
    for filename, metadata in active_sources.items():
        print(f"📄 {filename}")
        print(f"   Title: {metadata['title']}")
        print(f"   Organization: {metadata['organization']}")
        print(f"   License: {metadata.get('license', 'Not specified')}")
        
        output_path = sources_dir / filename
        
        # Check if file already exists and is valid
        if output_path.exists() and validate_pdf(output_path):
            existing_size = output_path.stat().st_size
            print(f"   ✓ File already exists and is valid ({existing_size:,} bytes)")
            print(f"   ⏭️  Skipping (delete file to re-download)")
            successful += 1
            print()
            continue
        
        # Special handling for known problematic sources
        url = metadata['url']
        if 'researchgate.net' in url.lower():
            print(f"   ⚠️  ResearchGate blocks automated downloads")
            print(f"   📥 Manual download required - please download manually and place in:")
            print(f"      {output_path}")
            skipped += 1
            print()
            continue
        
        # Download the file
        if download_pdf(url, output_path):
            successful += 1
        else:
            failed += 1
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 Download Summary:")
    print(f"   ✅ Successful: {successful}/{total}")
    if skipped > 0:
        print(f"   ⏭️  Skipped (manual required): {skipped}/{total}")
    if failed > 0:
        print(f"   ❌ Failed: {failed}/{total}")
    
    if failed == 0 and skipped == 0:
        print("🎉 All sources downloaded successfully!")
        return 0
    elif failed == 0:
        print(f"✅ All automated downloads successful ({skipped} require manual download)")
        return 0
    else:
        print("⚠️  Some downloads failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = download_all_sources()
    sys.exit(exit_code)
