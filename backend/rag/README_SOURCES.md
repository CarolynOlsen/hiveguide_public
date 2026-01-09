# RAG Sources Management

This document explains how to download and manage RAG sources for the HiveGuide chatbot.

## Downloading Sources

All source PDFs are configured in `backend/rag/config.py` in the `PDF_SOURCES` dictionary. To download all configured sources, run:

```bash
cd /workspace
PYTHONPATH=/workspace python3 backend/scripts/download_rag_sources.py
```

### Features

- **Automatic validation**: Downloads are validated to ensure they are real PDFs (checks magic bytes and file size)
- **Synced with config**: Dynamically reads from `config.py` to ensure sources match configuration
- **Corruption detection**: Rejects files smaller than 1KB or without valid PDF headers
- **Smart skipping**: Skips existing valid files (delete to force re-download)
- **Special handling**: Detects ResearchGate URLs and prompts for manual download

### Output

```
📊 Download Summary:
   ✅ Successful: 8/8
🎉 All sources downloaded successfully!
```

## Manual Downloads

Some sources (like ResearchGate) block automated downloads. For these:

1. Visit the URL in a browser
2. Download the PDF manually
3. Place it in `/workspace/rag/sources/` with the exact filename from `config.py`
4. Run the script again to verify

## Re-processing Sources

After downloading new sources or updating existing ones, regenerate embeddings:

```bash
cd /workspace
PYTHONPATH=/workspace python3 backend/scripts/populate_embeddings_langchain.py
```

This will:
1. Clear existing embeddings (684 chunks)
2. Process all PDFs in the sources directory
3. Generate embeddings using OpenAI
4. Store in PostgreSQL database
5. Verify all chunks have embeddings

## Source Validation

The download script validates each PDF:

- ✅ File size > 1KB
- ✅ Valid PDF magic bytes (`%PDF-`)
- ✅ Successful HTTP download (no 403/404 errors)

Invalid files are automatically rejected and deleted.

## Current Sources

See `backend/rag/sources_licensing.md` for detailed licensing information.

**Active Sources (8):**
1. Fall Management - Maine Department of Agriculture
2. Midwest Beekeeping in a Year - Center for Rural Affairs
3. Small Hive Beetle - Virginia Cooperative Extension
4. The Beekeeper's Handbook - Rudrappa, Kirankumar (CC-BY)
5. Tools for Varroa Management - Honey Bee Health Coalition
6. Varroa Mite Biology and Feeding Damage - Virginia Cooperative Extension
7. Varroa Mite Management Methods - Virginia Cooperative Extension
8. Varroa Mite Sampling Methods - Virginia Cooperative Extension

All sources are licensed for commercial use with proper attribution.
