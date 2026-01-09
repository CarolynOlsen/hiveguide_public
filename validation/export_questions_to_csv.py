#!/usr/bin/env python3
"""
Export existing generated questions to CSV format with ground truth information.
This allows iterating on strategies without regenerating questions.
"""
import argparse
import csv
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_PATH = PROJECT_ROOT / "validation" / "queries" / "generated_queries.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "validation" / "queries" / "questions_ground_truth.csv"


def export_questions_to_csv(
    input_path: Path,
    output_path: Path,
    limit: int | None = None,
):
    """Export questions from JSON to CSV with ground truth information."""
    # Load questions from JSON
    with open(input_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    
    if limit:
        questions = questions[:limit]
    
    print(f"Exporting {len(questions)} questions to CSV...")
    
    # Prepare CSV data
    csv_rows = []
    for q in questions:
        # Join list fields with semicolons for CSV
        ground_truth_chunks = ";".join(q.get("ground_truth_chunks", []))
        ground_truth_documents = ";".join(q.get("ground_truth_documents", []))
        expected_sources = ";".join(q.get("expected_sources", []))
        
        csv_rows.append({
            "query_id": q.get("query_id", ""),
            "question": q.get("question", ""),
            "question_type": q.get("ground_truth_intent", ""),  # general/personal/combined
            "generation_strategy": q.get("generation_strategy", ""),
            "source_material": ground_truth_documents,  # documents used to create the question
            "ground_truth_chunks": ground_truth_chunks,  # specific chunks
            "expected_sources": expected_sources,
            "requires_personal_data": str(q.get("requires_personal_data", False)).lower(),
        })
    
    # Write to CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        if csv_rows:
            fieldnames = list(csv_rows[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)
    
    print(f"✓ Exported {len(csv_rows)} questions to {output_path}")
    
    # Print summary by question type
    type_counts = {}
    for row in csv_rows:
        qtype = row["question_type"]
        type_counts[qtype] = type_counts.get(qtype, 0) + 1
    
    print("\nQuestion type distribution:")
    for qtype, count in sorted(type_counts.items()):
        print(f"  {qtype}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="Export generated questions to CSV with ground truth information."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(DEFAULT_INPUT_PATH),
        help=f"Path to input JSON file (default: {DEFAULT_INPUT_PATH})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Path to output CSV file (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of questions to export",
    )
    args = parser.parse_args()
    
    export_questions_to_csv(
        input_path=Path(args.input),
        output_path=Path(args.output),
        limit=args.limit,
    )


if __name__ == "__main__":
    main()

