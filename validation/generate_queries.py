import argparse
import json
import math
import os
import random
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

import openai
import logging

# Suppress verbose logging from HTTP clients and OpenAI
# Set this BEFORE importing or creating any OpenAI clients
os.environ.setdefault("OPENAI_LOG", "error")

logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("openai._client").setLevel(logging.WARNING)
logging.getLogger("stainless").setLevel(logging.WARNING)
logging.getLogger("stainless._client").setLevel(logging.WARNING)

# Paths and constants
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = PROJECT_ROOT / "backend" / "rag" / "sources"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "validation" / "queries" / "generated_queries.json"
# Use the same model family as response generation for cost efficiency (query generation requires passing document context)
DEFAULT_MODEL = "openai/gpt-oss-120b"

# Chunks are loaded from database, so no text splitter needed

QUESTION_COUNT_PER_CHUNK = 3
SQL_QUESTION_COUNT = 12
COMBINED_QUESTION_COUNT = 12


@dataclass
class QueryRecord:
    query_id: str
    question: str
    ground_truth_intent: str
    generation_strategy: str
    expected_sources: List[str]
    ground_truth_chunks: List[str] = field(default_factory=list)
    ground_truth_documents: List[str] = field(default_factory=list)
    requires_personal_data: bool = False
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


def get_client() -> openai.OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is required to generate queries.")
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )


def load_pdf_chunks(max_docs: Optional[int] = None, max_chunks_per_doc: Optional[int] = None, seed: Optional[int] = None):
    """Load PDF chunks from the database (where they're stored with embeddings).
    
    Args:
        max_docs: Limit number of documents to sample
        max_chunks_per_doc: Limit chunks per document
        seed: Random seed for reproducible chunk ordering (default: None for random)
    """
    from validation.services.db import SessionLocal
    from validation.services.models import DocumentChunk
    
    db = SessionLocal()
    try:
        # Query chunks that have embeddings (i.e., are ready to use)
        query = db.query(DocumentChunk).filter(
            DocumentChunk.embedding_vector.isnot(None)
        ).order_by(DocumentChunk.document_title, DocumentChunk.chunk_position)
        
        all_chunks = query.all()
        
        # Group by document title
        chunks_by_doc = {}
        for chunk in all_chunks:
            doc_title = chunk.document_title or "unknown"
            if doc_title not in chunks_by_doc:
                chunks_by_doc[doc_title] = []
            chunks_by_doc[doc_title].append(chunk)
        
        # Limit documents if requested
        if max_docs:
            doc_titles = sorted(chunks_by_doc.keys())[:max_docs]
        else:
            doc_titles = sorted(chunks_by_doc.keys())
        
        chunks = []
        for doc_title in doc_titles:
            doc_chunks = chunks_by_doc[doc_title]
            # Limit chunks per doc if requested
            if max_chunks_per_doc:
                doc_chunks = doc_chunks[:max_chunks_per_doc]
            
            for chunk in doc_chunks:
                # Extract filename from source_url if possible, otherwise use document_title
                source_url = chunk.source_url or ""
                filename = source_url.split("/")[-1] if "/" in source_url else chunk.document_title or "unknown.pdf"
                if not filename.endswith(".pdf"):
                    filename = f"{filename}.pdf"
                
                chunks.append(
                    {
                        "doc_path": filename,
                        "chunk_id": f"{filename}#chunk_{chunk.chunk_position}",
                        "text": chunk.chunk_text or "",
                    }
                )
        
        # Filter out non-useful chunks (copyright, TOC, etc.)
        chunks = [chunk for chunk in chunks if is_useful_chunk(chunk)]
        
        # Randomize the order of chunks for more diverse question generation
        if seed is not None:
            random.seed(seed)
        random.shuffle(chunks)
        
        return chunks
    finally:
        db.close()


def is_useful_chunk(chunk: dict) -> bool:
    """Filter out chunks that are unlikely to generate useful questions.
    
    Skips chunks that are:
    - Too short (< 50 characters) 
    - Copyright/legal notices
    - Table of contents
    - Headers/footers only
    - Mostly whitespace or special characters
    """
    text = chunk.get("text", "").strip()
    
    # Skip very short chunks
    if len(text) < 50:
        return False
    
    # Skip chunks that are mostly whitespace or special characters
    if len(text.replace(" ", "").replace("\n", "")) < 30:
        return False
    
    text_lower = text.lower()
    
    # Skip copyright/legal notices
    copyright_indicators = [
        "copyright",
        "©",
        "all rights reserved",
        "permission to reproduce",
        "license",
        "prohibited",
        "unauthorized",
    ]
    if any(indicator in text_lower for indicator in copyright_indicators):
        # But allow if it's part of a larger informative chunk (e.g., mentions copyright but has content)
        if len(text) < 200:  # Short chunks with copyright are likely just notices
            return False
    
    # Skip table of contents
    toc_indicators = [
        "table of contents",
        "contents",
        "page",
    ]
    # Only skip if it's very short and looks like a TOC (lots of page numbers or dots)
    if any(indicator in text_lower for indicator in toc_indicators):
        if len(text) < 300 and (text.count("...") > 3 or text.count("page") > 2):
            return False
    
    # Skip chunks that are mostly page numbers or headers
    if len(text.split()) < 10:  # Very few words
        return False
    
    return True


def call_llm(client: openai.OpenAI, prompt_model: str, prompt: str, temperature: float = 0.7, timeout: float = 60.0):
    """Call LLM with timeout to prevent hanging."""
    resp = client.chat.completions.create(
        model=prompt_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=800,
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()


def parse_json_list(content: str) -> List[str]:
    """Parse JSON array from LLM output; return [] on failure.
    Handles JSON wrapped in markdown code blocks (```json ... ```).
    """
    if not content:
        return []
    cleaned = content.strip()
    
    # Remove markdown code blocks if present (```json ... ``` or ``` ... ```)
    if cleaned.startswith("```"):
        # Find the closing ```
        end_marker = cleaned.find("```", 3)
        if end_marker != -1:
            # Extract content between markers
            cleaned = cleaned[3:end_marker].strip()
        else:
            # No closing marker found (content might be truncated), extract from after opening
            cleaned = cleaned[3:].strip()
        # Remove "json" if it's the first word after opening ```
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    
    # Try to extract the first [...] block, even if prefixed with tokens like "array."
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    candidate_blocks = []
    if start != -1 and end != -1 and end > start:
        candidate_blocks.append(cleaned[start : end + 1])
    candidate_blocks.append(cleaned)  # fallback to full content

    for block in candidate_blocks:
        try:
            data = json.loads(block)
            if isinstance(data, list):
                return [str(x) for x in data if isinstance(x, (str, int, float))]
        except Exception:
            continue
    return []


def _pdf_prompt(chunk: dict, question_count: int) -> str:
    return f"""
You are helping generate evaluation questions for a beekeeping RAG system.
Given this source chunk, write {question_count} natural beekeeping questions a beginner beekeeper might ask.

Chunk (source: {chunk["doc_path"]}, id: {chunk["chunk_id"]}):
\"\"\"{chunk["text"]}\"\"\"

CRITICAL RULES:
- Ask ONE clear question per question, not multiple hidden questions
- Don't reference sources, document names, or "the guide" - users don't care where the answer comes from
- Be natural and conversational, like a beekeeper would actually ask
- Focus on practical beekeeping questions, not meta-questions about the document
- If this chunk doesn't contain useful beekeeping information (e.g., copyright, table of contents, headers only), return an empty array: []

Return ONLY a JSON array of strings. Return [] if the chunk isn't useful for generating questions.
""".strip()


def _generate_pdf_chunk_questions(client, chunk, question_count, model) -> List[QueryRecord]:
    """Generate general (documents-only) questions from a chunk."""
    prompt = _pdf_prompt(chunk, question_count)
    try:
        content = call_llm(client, prompt_model=model, prompt=prompt, timeout=120)
        questions = parse_json_list(content)
    except Exception:
        return []

    records = []
    for q in questions:
        records.append(
            QueryRecord(
                query_id=str(uuid.uuid4()),
                question=q,
                ground_truth_intent="general",
                generation_strategy="pdf_chunk",
                expected_sources=["documents"],
                ground_truth_chunks=[chunk["chunk_id"]],
                ground_truth_documents=[chunk["doc_path"]],
                requires_personal_data=False,
            )
        )
    return records


def _generate_combined_question_from_chunk(client, chunk, model) -> Optional[QueryRecord]:
    """Generate a single combined question from a chunk."""
    prompt = _combined_prompt(chunk)
    try:
        content = call_llm(client, prompt_model=model, prompt=prompt, timeout=120)
        questions = parse_json_list(content)
        if not questions:
            return None
        q = questions[0]
        return QueryRecord(
            query_id=str(uuid.uuid4()),
            question=q,
            ground_truth_intent="combined",
            generation_strategy="combined_nshot",
            expected_sources=["personal_data", "documents"],
            ground_truth_chunks=[chunk["chunk_id"]],
            ground_truth_documents=[chunk["doc_path"]],
            requires_personal_data=True,
        )
    except Exception:
        return None


def generate_questions_from_chunks(
    client: openai.OpenAI,
    model: str,
    chunks: List[dict],
    general_count: int = None,
    combined_count: int = None,
    max_workers: int = 4,
    output_path: Path = None,
    existing_records: List[QueryRecord] = None,
) -> Tuple[List[QueryRecord], List[QueryRecord]]:
    """
    Generate both general and combined questions from the same chunks efficiently.
    Returns (general_records, combined_records).
    """
    general_records: List[QueryRecord] = []
    combined_records: List[QueryRecord] = []
    save_interval = 5
    last_saved_count = 0
    current_existing = existing_records or []
    
    # Determine target counts
    needed_general = general_count or 0
    needed_combined = combined_count or 0
    if needed_general == 0 and needed_combined == 0:
        return [], []
    
    # We'll process chunks in a cycle until we reach both target counts
    # This ensures we continue even if some chunks fail
    chunk_cycle = chunks if chunks else []
    
    def process_chunk(chunk):
        """Process a single chunk to generate both question types."""
        general_qs = []
        combined_q = None
        
        # Always try to generate both types - we'll limit later
        try:
            general_qs = _generate_pdf_chunk_questions(client, chunk, 1, model)
        except Exception:
            pass
        
        try:
            combined_q = _generate_combined_question_from_chunk(client, chunk, model)
        except Exception:
            pass
        
        return general_qs, combined_q
    
    # Process chunks in batches, continuing until we reach target counts
    # Cycle through chunks if needed to ensure we can reach targets even with failures
    chunk_index = 0
    processed_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        
        def submit_chunk():
            """Submit next chunk for processing if we haven't reached targets."""
            nonlocal chunk_index
            if not chunk_cycle:
                return False
            
            # Check if we need more chunks
            need_general = general_count and len(general_records) < general_count
            need_combined = combined_count and len(combined_records) < combined_count
            
            if not need_general and not need_combined:
                return False
            
            # Get next chunk (cycle if needed)
            chunk = chunk_cycle[chunk_index % len(chunk_cycle)]
            future = executor.submit(process_chunk, chunk)
            futures[future] = chunk_index
            chunk_index += 1
            return True
        
        # Submit initial batch
        while len(futures) < max_workers and submit_chunk():
            pass
        
        with tqdm(desc="Processing chunks", unit="chunk") as pbar:
            while futures:
                # Wait for at least one future to complete
                done = []
                for future in list(futures.keys()):
                    if future.done():
                        done.append(future)
                
                if not done:
                    # Wait for futures to complete
                    import time
                    time.sleep(0.1)
                    continue
                
                # Process completed futures
                for future in done:
                    idx = futures.pop(future)
                    try:
                        gen_qs, comb_q = future.result(timeout=1)
                        
                        # Add general questions (limit to target)
                        if gen_qs:
                            for q in gen_qs:
                                if not general_count or len(general_records) < general_count:
                                    general_records.append(q)
                        
                        # Add combined question (limit to target)
                        if comb_q and (not combined_count or len(combined_records) < combined_count):
                            combined_records.append(comb_q)
                        
                        processed_count += 1
                        pbar.update(1)
                        pbar.set_postfix({
                            "general": len(general_records),
                            "combined": len(combined_records),
                            "processed": processed_count
                        })
                        
                        # Incremental save every ~5 records
                        all_new = general_records + combined_records
                        if output_path and len(all_new) - last_saved_count >= save_interval:
                            current_existing = save_records_incremental(all_new, output_path, current_existing)
                            last_saved_count = len(all_new)
                    except Exception as e:
                        processed_count += 1
                        pbar.update(1)
                        # Continue processing even if this chunk failed
                
                # Submit more chunks if we haven't reached targets
                while len(futures) < max_workers and submit_chunk():
                    pass
                
                # Check if we've reached both targets
                if (not general_count or len(general_records) >= general_count) and \
                   (not combined_count or len(combined_records) >= combined_count):
                    # Cancel remaining futures
                    for future in futures:
                        future.cancel()
                    break
                    continue
    
    return general_records, combined_records


def generate_sql_questions(
    client: openai.OpenAI, 
    model: str, 
    sql_question_count: int,
    output_path: Path = None,
    existing_records: List[QueryRecord] = None,
) -> List[QueryRecord]:
    schema_description = """
Tables:
- hives(id, nickname, location, description, user_id)
- inspections(id, hive_id, timestamp/inspection_date, notes, transcription, weather, temperature, queen_visible, eggs_visible, larvae_visible, capped_brood_visible, laying_pattern, activity_level, action_items)

Context:
- Each user has multiple hives.
- Inspections reference hives via hive_id.
- Questions should reference the user's own data ("my hives", "my inspections").
"""
    records = []
    save_interval = 5
    last_saved_count = 0
    current_existing = existing_records or []
    
    # Batch generation to avoid overwhelming the LLM (generate 20 at a time)
    batch_size = 20
    batches = (sql_question_count + batch_size - 1) // batch_size
    
    with tqdm(desc="Generating SQL questions", total=sql_question_count, unit="question") as pbar:
        for batch_idx in range(batches):
            batch_count = min(batch_size, sql_question_count - len(records))
            if batch_count <= 0:
                break
                
            prompt = f"""
Generate {batch_count} realistic questions a beekeeper would ask that require knowledge about their personal hive data:
{schema_description}

Examples of good personal questions:
- "I'm heading to my Franksville hives, what were my next action items?"
- "What were my latest hive weights?"
- "Which of my hives have I treated for varroa this year?"
- "What was my brood pattern like for Hillcrest 2, on my last inspection?"

CRITICAL RULES:
- Reference the user's own data ("my hives", "my inspections", etc.) but DON'T assume they know specific details
- Ask the system to LOOK UP the data, don't state what the data shows (e.g., "Based on my recent inspections..." not "Given that my logs show...")
- Ask about specific hive data (inspections, weights, treatments, brood patterns, action items, etc.)
- Ask ONE clear question, not multiple hidden questions
- You can reference Franksville or Hillcrest apiaries, but don't make up other apiaries (e.g. "during my inspection at the orchard")
- Be natural and conversational, like a beekeeper would actually ask
- Don't reference sources or "the guide" - users don't care where the answer comes from
- Don't assume the user remembers specific dates 

BAD EXAMPLE: "Given that my weight logs show the super on Hive #3 is about 70% drawn as of early August and floral resources are starting to dip, when is the optimal time to harvest the honey according to the guide, and what indoor temperature should I maintain for faster extraction?"
- Assumes user knows specific data (should ask system to look it up)
- References "the guide" (users don't care about sources)
- Asks multiple questions (harvest timing AND temperature)

GOOD EXAMPLE: "Based on my recent inspections and it being July, when should I plan to harvest honey?"
- Asks system to look up data ("Based on my recent inspections")
- Doesn't reference sources
- Asks one clear question

Return ONLY a JSON array of strings. Each question should be a string in the array.
Example format: ["Question 1?", "Question 2?", "Question 3?"]
""".strip()
            
            try:
                content = call_llm(client, prompt_model=model, prompt=prompt, timeout=120)
            except Exception as e:
                tqdm.write(f"Warning: SQL question generation batch {batch_idx + 1} failed: {e}")
                continue
            
            questions = parse_json_list(content)
            if not questions:
                tqdm.write(f"Warning: SQL question generation batch {batch_idx + 1} returned no questions. Raw LLM output (first 500 chars): {content[:500]}")
                continue
            
            for q in questions:
                if len(records) >= sql_question_count:
                    break
                records.append(
                    QueryRecord(
                        query_id=str(uuid.uuid4()),
                        question=q,
                        ground_truth_intent="personal",
                        generation_strategy="sql_schema",
                        expected_sources=["personal_data"],
                        requires_personal_data=True,
                    )
                )
                pbar.update(1)
                pbar.set_postfix({"total": len(records)})
                
                # Incremental save every ~5 records
                if output_path and len(records) - last_saved_count >= save_interval:
                    current_existing = save_records_incremental(records, output_path, current_existing)
                    last_saved_count = len(records)
    
    return records


COMBINED_EXAMPLES = [
    "Based on my recent inspections and it being July, when should I plan to harvest honey?",
    "Based on my recent weights, which of my hives need more feed before winter?",
    "What were my recent varroa test results, and how do they compare to treatment thresholds?",
]


def _combined_prompt(chunk: dict) -> str:
    examples = "\n".join([f"- {ex}" for ex in COMBINED_EXAMPLES])
    return f"""
You are helping generate evaluation questions for a beekeeping RAG system.
Using BOTH the user's personal hive data AND this authoritative document chunk, write 1 natural question that truly needs both:
- It should reference personal data (e.g., "my hive", "my inspections", "my weight records")
- It should also require factual guidance from the document chunk below.

Chunk (source: {chunk["doc_path"]}, id: {chunk["chunk_id"]}):
\"\"\"{chunk["text"]}\"\"\"

CRITICAL RULES:
- Ask the system to LOOK UP the user's data, don't state what the data shows (e.g., "Based on my recent inspections..." not "Given that my logs show...")
- Ask ONE clear question per question
- Don't reference sources, "the guide", or document names
- Be natural and conversational, like a beekeeper would actually ask
- If this chunk doesn't contain useful beekeeping information (e.g., copyright, table of contents, headers only), return an empty array: []

BAD EXAMPLE: "Given that my weight logs show the super on Hive #3 is about 70% drawn as of early August and floral resources are starting to dip, when is the optimal time to harvest the honey according to the guide, and what indoor temperature should I maintain for faster extraction?"
- Assumes user knows specific data (the system will look up the data)
- References "the guide" (users don't care about sources)
- Asks multiple questions (harvest timing AND temperature)

GOOD EXAMPLES:
{examples}

Return ONLY a JSON array with exactly 1 question, or [] if the chunk isn't useful.
""".strip()




def load_existing_records(output_path: Path) -> List[QueryRecord]:
    """Load existing records from file if it exists."""
    if not output_path.exists():
        return []
    try:
        with open(output_path, "r") as f:
            data = json.load(f)
            return [QueryRecord(**item) for item in data]
    except Exception:
        return []


def save_records(records: List[QueryRecord], output_path: Path) -> None:
    """Save all records to file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in records], f, indent=2, ensure_ascii=False)


def save_records_incremental(new_records: List[QueryRecord], output_path: Path, existing_records: List[QueryRecord] = None):
    """Save records incrementally, appending to existing records."""
    if existing_records is None:
        existing_records = load_existing_records(output_path)
    
    # Combine existing and new records
    all_records = existing_records + new_records
    
    # Save to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([r.to_dict() for r in all_records], f, indent=2, ensure_ascii=False)
    
    return all_records


def _truncate(records: List[QueryRecord], max_count: Optional[int]) -> List[QueryRecord]:
    if max_count is None or len(records) <= max_count:
        return records
    return random.sample(records, max_count)


def main():
    parser = argparse.ArgumentParser(description="Generate validation queries.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Output path for queries JSON")
    parser.add_argument("--general-count", type=int, default=None, help="Limit number of general (PDF) queries")
    parser.add_argument("--personal-count", type=int, default=None, help="Limit number of personal (SQL) queries")
    parser.add_argument("--combined-count", type=int, default=None, help="Limit number of combined queries")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help=f"Model for generation (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-workers", type=int, default=4, help="Max threads for PDF chunk generation")
    parser.add_argument("--max-docs", type=int, default=None, help="Limit number of PDFs to sample")
    parser.add_argument("--max-chunks-per-doc", type=int, default=5, help="Max chunks per PDF to sample")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible chunk ordering")
    parser.add_argument("--questions-per-chunk", type=int, default=QUESTION_COUNT_PER_CHUNK, help="Questions per PDF chunk")
    parser.add_argument("--sql-question-count", type=int, default=None, help="Total SQL/personal questions")
    parser.add_argument("--combined-question-count", type=int, default=None, help="Total combined questions")
    args = parser.parse_args()

    client = get_client()

    chunks = load_pdf_chunks(max_docs=args.max_docs, max_chunks_per_doc=args.max_chunks_per_doc, seed=args.seed)

    # Align question counts
    sql_question_count = args.sql_question_count or args.personal_count or SQL_QUESTION_COUNT
    general_count = args.general_count
    combined_count = args.combined_count or args.combined_question_count

    # Load existing records to support incremental saving and resumption
    existing_records = load_existing_records(args.output)
    if existing_records:
        tqdm.write(f"Found {len(existing_records)} existing records, will append new ones")

    # Generate general and combined questions from the same chunks efficiently
    pdf_records, combined_records = generate_questions_from_chunks(
        client=client,
        model=args.model,
        chunks=chunks,
        general_count=general_count,
        combined_count=combined_count,
        max_workers=args.max_workers,
        output_path=args.output,
        existing_records=existing_records,
    )
    # Update existing_records with PDF and combined records
    if args.output:
        all_chunk_records = pdf_records + combined_records
        existing_records = save_records_incremental(all_chunk_records, args.output, existing_records)
    
    # Generate personal/SQL questions separately
    sql_records = generate_sql_questions(
        client=client,
        model=args.model,
        sql_question_count=sql_question_count,
        output_path=args.output,
        existing_records=existing_records,
    )
    # Update existing_records with SQL records
    if args.output:
        existing_records = save_records_incremental(sql_records, args.output, existing_records)

    pdf_records = _truncate(pdf_records, args.general_count)
    sql_records = _truncate(sql_records, args.personal_count)
    combined_records = _truncate(combined_records, args.combined_count)

    all_records = pdf_records + sql_records + combined_records
    # Final save with all records (truncated if needed)
    save_records(all_records, args.output)
    tqdm.write(
        f"\n✓ Generated {len(all_records)} queries "
        f"(general={len(pdf_records)}, personal={len(sql_records)}, combined={len(combined_records)}) "
        f"to {args.output}"
    )


if __name__ == "__main__":
    main()

