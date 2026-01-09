# Validation Testing System

This directory contains a comprehensive quantitative validation system for the multi-source RAG architecture with LLM-based classification. The system generates synthetic queries, executes them against different strategies, and collects detailed metrics for evaluation.

**This validation system reproduces the results from:**  
**"Comparative Evaluation of Intent Routing Strategies for Multi-Source RAG"**  
See: `../publications/strategies_comparison.pdf`

## Overview

The validation system tests the RAG bot's ability to:
1. **Classify user intent** into three categories: `personal_only`, `documents_only`, or `both_combined`
2. **Route queries** to appropriate data sources (SQL for personal data, vector search for documents, or both)
3. **Retrieve relevant information** from the correct sources
4. **Generate accurate responses** with proper citations

## Quick Start

### Workflow Overview

The validation system has **three separate steps**:

1. **Test Data Setup** (one-time - create test user with hives and inspections)
2. **Query Generation** (one-time or when you need new questions)
3. **Running Validation** (iterative - test different strategies on the same questions)

### Step 0: Create Test Data (One-Time Setup)

Create a test user with realistic hives and inspection data:

```bash
# Create test user with default validation email
python3 validation/seed_validation_data.py \
    --email validation-test@test.com \
    --password testpassword123

# Use a different email
python3 validation/seed_validation_data.py \
    --email my-test@test.com \
    --password mypassword

# Recreate test data (deletes existing user first)
python3 validation/seed_validation_data.py \
    --email validation-test@test.com \
    --password testpassword123 \
    --reseed
```

**What it creates:**
- Test user account (pre-approved)
- 4 hives with realistic names and locations
- ~30 inspections spread over the past 8 months
- Rich inspection data (queen status, brood patterns, action items, etc.)

**Note:** The validation script will check for this data and error if missing. You only need to run this once (or when you want to reset test data).

### Step 1: Generate Questions (One-Time Setup)

Generate questions with ground truth. The script generates three types of queries:
1. **General queries** (from PDF chunks) - Intent: `documents_only`
2. **Personal queries** (from SQL schema) - Intent: `personal_only`
3. **Combined queries** (n-shot examples) - Intent: `both_combined`

```bash
# Generate with default counts
python3 validation/generate_queries.py

# Customize question counts
python3 validation/generate_queries.py \
    --general-count 100 \              # Limit number of general (PDF) queries
    --personal-count 50 \              # Limit number of personal (SQL) queries
    --combined-count 50                # Limit number of combined queries

# Additional options
python3 validation/generate_queries.py \
    --max-docs 10 \                    # Limit number of PDFs to sample
    --max-chunks-per-doc 5 \           # Max chunks per PDF to sample (default: 5)
    --questions-per-chunk 3 \          # Questions per PDF chunk (default: 3)
    --model "openai/gpt-oss-120b" \    # Model for generation (default: openai/gpt-oss-120b)
    --output validation/queries/generated_queries.json  # Output path

# Export to CSV for easier iteration
python3 validation/export_questions_to_csv.py
```

**Note:** Questions are saved to `validation/queries/generated_queries.json`. The script supports resuming if interrupted (saves incrementally), but the final output replaces the file.

### Step 2: Run Validation (Iterative)

Run validation using existing questions. The script automatically loads configuration from `config.yaml` and uses `validation-test@test.com` as the default test user.

**By default, the script runs all 7 strategies and starts fresh (ignores existing results).**

```bash
# Run all 7 default strategies (fresh run - ignores existing results)
python3 validation/run_strategy_validation.py

# Resume from existing results (skip already processed queries)
python3 validation/run_strategy_validation.py --resume

# Limit number of questions (useful for quick testing)
# Note: Questions are randomly sampled with a fixed seed (42) to ensure diverse question types
python3 validation/run_strategy_validation.py --limit 50

# Use a different test user (optional)
python3 validation/run_strategy_validation.py --email other-test@test.com
```

### Strategy-Based Validation (For Iteration)

By default, the script runs all 7 strategies:
- `llm_classifier` - LLM-based intent classification (GPT-4o with few-shot prompting)
- `heuristic_classifier` - Keyword-based heuristics for classification
- `supervised_classifier` - LightGBM model trained on labeled examples
- `embedding_router` - k-NN classification using embedding similarity
- `agent_discretion` - ReAct-style agent with dynamic tool selection
- `agent_with_intent_tool` - Agent with a dedicated intent classification tool
- `always_both` - Baseline that always uses both document search and user data tools

```bash
# Run all default strategies (fresh run)
python3 validation/run_strategy_validation.py

# Run a single strategy
python3 validation/run_strategy_validation.py \
    --strategy llm_classifier

# Compare specific strategies
python3 validation/run_strategy_validation.py \
    --strategy llm_classifier \
    --strategy heuristic_classifier \
    --limit 20

# Resume from existing results
python3 validation/run_strategy_validation.py --resume
```

## Self-Contained Validation System

**The validation system is fully self-contained** in `validation/services/`. All necessary components have been copied from the app, allowing you to modify them freely for strategy testing **without affecting the main application**.

### Key Files to Modify

- **`validation/services/rag_service.py`** - **MAIN FILE TO MODIFY** for strategy testing
  - Contains `query_with_user_tools()` with custom parameters
  - Includes intent classification logic
  - Can be freely modified without affecting the app

- **`validation/services/config.py`** - Validation configuration (can be modified independently)

- **`validation/services/user_data_tool.py`** - User data tool (can be modified for testing)

### Adding a New Strategy

1. **Modify `validation/services/rag_service.py`**:
   ```python
   def query_with_user_tools(
       self, 
       question: str, 
       user_id: int, 
       session_id: Optional[str] = None,
       my_custom_heuristic: bool = False,  # ADD YOUR PARAMETER
   ) -> Dict[str, Any]:
       if my_custom_heuristic:
           # Your custom logic here
           ...
   ```

2. **Create a strategy class** in `run_strategy_validation.py`:
   ```python
   class MyCustomStrategy(ValidationStrategy):
       def __init__(self):
           self.service = get_validation_rag_service()
       
       @property
       def name(self) -> str:
           return "my_custom_strategy"
       
       def execute_query(self, question, user_id, session_id=None):
           result = self.service.query_with_user_tools(
               question=question,
               user_id=user_id,
               session_id=session_id,
               my_custom_heuristic=True,  # Your custom parameter
           )
           return result
   ```

3. **Register and run**:
   ```python
   register_strategy(MyCustomStrategy)
   ```
   ```bash
   python3 validation/run_strategy_validation.py --strategy my_custom_strategy --email test@test.com
   ```

## Built-in Strategies

1. **`llm_classifier`**: LLM-based classification using GPT-4o with few-shot prompting
2. **`heuristic_classifier`**: Rule-based keyword matching
3. **`supervised_classifier`**: LightGBM model trained on TF-IDF features
4. **`embedding_router`**: k-NN classification using embedding similarity
5. **`agent_discretion`**: ReAct-style agent with dynamic tool selection (no pre-classification)
6. **`agent_with_intent_tool`**: Agent with access to an intent classification tool it can call when uncertain
7. **`always_both`**: Baseline that always uses both tools (no classification)

## Architecture and Rationale

### Model Selection Strategy

We use **different models for different purposes** to optimize for both accuracy and cost:

#### Intent Classification: `openai/gpt-4o`
- Supports logprobs (required for confidence scores and ROC-AUC metrics)
- Minimal tokens (~30-50 per classification vs. 5,000+ for full RAG response)
- Cost: ~$0.075 per 1,000 queries (minimal compared to full RAG costs)

#### Query Generation: `anthropic/claude-haiku-4.5` (default)
- Different model family (Anthropic) than system being tested (OpenAI) to avoid bias
- Tests system's generalization to diverse query styles

#### Chat Responses: `openai/gpt-oss-120b`
- Primary model used in production
- Provides high-quality responses with RAG context

### Baseline Systems

1. **Always-Both**: Bypasses intent classification, always uses both tools
2. **Agent-Discretion**: No pre-classification, agent decides which tools to use

## Validation Pipeline

### Step 0: Test Data Setup

**Script:** `seed_validation_data.py`

See **Step 0: Create Test Data** in Quick Start above for usage and examples.

**Script:** `prepare_sources.py` (Optional - only if PDF sources missing)
- Downloads PDF sources to `backend/rag/sources/`
- Generates embeddings (idempotent)

### Step 1: Query Generation

**Script:** `generate_queries.py`

See **Step 1: Generate Questions** in Quick Start above for usage and parameters.

#### Ground Truth Location

The ground truth (questions with their expected intents, source chunks, and documents) is stored in:

- **Primary format (JSON):** `validation/queries/generated_queries.json`
  - Full structured data with all metadata
  - Used by validation scripts directly
  
- **Exported format (CSV):** `validation/queries/questions_ground_truth.csv`
  - Human-readable format for review and iteration
  - Exported from JSON using `export_questions_to_csv.py`

#### Adding Additional Questions to Ground Truth

To add more questions to the existing ground truth set:

**Option 1: Manual Addition (Recommended for small additions)**

1. **Add to CSV** (easiest for manual editing):
   ```bash
   # Edit the CSV file directly
   # Add rows with columns: query_id, question, question_type, generation_strategy, 
   #                        source_material, ground_truth_chunks, expected_sources, requires_personal_data
   ```

2. **Convert CSV back to JSON** (if needed):
   - The validation scripts can read CSV directly, so this may not be necessary
   - Or manually add to `generated_queries.json` following the same structure

**Option 2: Generate and Merge**

1. **Generate new questions to a temporary file:**
   ```bash
   python3 validation/generate_queries.py \
       --output validation/queries/new_questions.json \
       --general-count 10 \
       --personal-count 5 \
       --combined-count 5
   ```

2. **Manually merge** the JSON files or write a simple script to combine them:
   ```python
   import json
   from pathlib import Path
   
   # Load existing
   with open("validation/queries/generated_queries.json") as f:
       existing = json.load(f)
   
   # Load new
   with open("validation/queries/new_questions.json") as f:
       new = json.load(f)
   
   # Combine (deduplicate by query_id if needed)
   combined = existing + new
   
   # Save
   with open("validation/queries/generated_queries.json", "w") as f:
       json.dump(combined, f, indent=2)
   ```

3. **Re-export to CSV:**
   ```bash
   python3 validation/export_questions_to_csv.py
   ```

**Export to CSV:**
```bash
# Export all questions from JSON to CSV
python3 validation/export_questions_to_csv.py

# Export with limit
python3 validation/export_questions_to_csv.py --limit 100

# Export from custom input/output paths
python3 validation/export_questions_to_csv.py \
    --input validation/queries/generated_queries.json \
    --output validation/queries/questions_ground_truth.csv
```

This exports all questions with ground truth to `queries/questions_ground_truth.csv` for reuse across iterations.

### Step 2: Run Validation (Iterative)

**Script:** `run_strategy_validation.py`
- Run any registered strategy
- Compare multiple strategies side-by-side
- Default strategies: llm_classifier, always_both (add agent_discretion with `--run-agent-discretion`)
- Uses existing questions by default (from `generated_queries.json` or CSV)
- Automatically checks for test data and errors if missing

### Step 3: Metrics Calculation

**Script:** `metrics.py`

Computes:
- **Intent Classification**: Precision, Recall, F1, ROC-AUC
- **Retrieval Quality**: Precision@3, @5, @10
- **Response Quality** (RAGAS): Answer relevancy, faithfulness
- **Latency**: Mean, median, p95, p99

**Output:** `results/metrics_summary.json`

## Running Validation

### Configuration

The validation script automatically loads configuration from `config.yaml` in the project root. You can also set environment variables, which take precedence:

```yaml
# config.yaml
database_url: postgresql://...
openrouter_api_key: sk-or-v1-...
openai_api_key: sk-...  # Only needed if embeddings missing
```

Or set environment variables (which override config.yaml):
```bash
export DATABASE_URL="postgresql://..."
export OPENROUTER_API_KEY="sk-or-v1-..."
export OPENAI_API_KEY="sk-..."  # Only needed if embeddings missing
```

**Note:** The script uses `validation-test@test.com` as the default test user. Make sure this user exists (run `seed_validation_data.py` if needed).

### Using CSV Questions 

```bash
# Export questions once
python3 validation/export_questions_to_csv.py

# Use CSV for all strategy iterations
python3 validation/run_strategy_validation.py \
    --strategy my_strategy \
    --queries-file validation/queries/questions_ground_truth.csv
```

## Output Files

### Ground Truth Files

**`queries/generated_queries.json`** (Primary ground truth)
- All generated queries with complete ground truth metadata
- Structure:
  - `query_id`: Unique identifier
  - `question`: The question text
  - `ground_truth_intent`: Expected intent (`personal`, `general`, or `combined`)
  - `ground_truth_chunks`: List of chunk IDs that should be retrieved
  - `ground_truth_documents`: List of source documents
  - `generation_strategy`: How the question was generated (`pdf_chunk`, `sql_schema`, `combined`)
  - `expected_sources`: Expected source types (`documents`, `personal_data`, or both)
  - `requires_personal_data`: Boolean flag

**`queries/questions_ground_truth.csv`** (Exported ground truth)
- Human-readable CSV format exported from JSON
- Same information as JSON, formatted for easy review/editing
- Columns: `query_id`, `question`, `question_type`, `generation_strategy`, `source_material`, `ground_truth_chunks`, `expected_sources`, `requires_personal_data`
- Use this for manual editing or review

### `results/{strategy}_results.json`
- Full results for each strategy
- Includes: predicted intent, class probabilities, sources, latency, answer

### `results/metrics_summary.json`
- Aggregated metrics comparing all strategies

## File Structure

```
validation/
├── README.md                       # This file
├── run_strategy_validation.py     # Main validation script (runs all 7 strategies)
├── generate_queries.py            # Generate validation queries with ground truth
├── metrics.py                     # Compute all metrics (Hit@k, RAGAS, latency, cost)
├── seed_validation_data.py        # Create test user with hives/inspections
├── prepare_sources.py             # Download and process PDF sources
├── agent_with_intent_tool.py      # Agent with intent tool strategy
├── create_embedding_router.py     # Create embedding similarity router
├── embedding_router.py            # Embedding-based routing implementation
├── export_questions_to_csv.py     # Export queries to CSV format
├── rag_client.py                  # RAG client wrapper
├── services/                      # Self-contained validation services
│   ├── __init__.py
│   ├── config.py                  # Configuration management
│   ├── db.py                      # Database connection
│   ├── models.py                  # Database models
│   ├── rag_service.py             # RAG service with all strategy implementations
│   └── user_data_tool.py          # User data tool for personal queries
├── queries/                       # Validation queries with ground truth
│   ├── generated_queries.json     # 501 queries used in paper
│   ├── questions_ground_truth.csv # CSV export
│   ├── questions_ground_truth_train.csv  # Training split (optional)
│   └── questions_ground_truth_test.csv   # Test split (optional)
├── models/                        # Trained models for supervised/embedding strategies
│   ├── tfidf_vectorizer.pkl
│   ├── question_type_classifier_lgbm.txt
│   ├── label_encoder.pkl
│   ├── class_mapping.pkl
│   └── embedding_routing_index.pkl
└── results/                       # Example results from paper
    └── final/
        ├── llm_classifier_results.json
        ├── heuristic_classifier_results.json
        ├── supervised_classifier_results.json
        ├── embedding_router_results.json
        ├── agent_discretion_results.json
        ├── agent_with_intent_tool_results.json
        ├── always_both_results.json
        ├── strategy_metrics_summary.json
        └── summary_table.csv
```

## Key Design Decisions

### Why Logprobs for Intent Classification?
- ROC-AUC requires probability distributions, not just hard labels
- Logprobs provide calibrated confidence scores
- Enables analysis of classification uncertainty

### Why Separate Intent Classification Model?
- Provider compatibility: Most OpenRouter providers don't support logprobs
- Cost efficiency: Intent classification is tiny (question only, no RAG context)
- Reliability: `gpt-4o` consistently supports logprobs through OpenAI provider

### Why Different Model Family for Query Generation?
- Avoids bias: Using the same model to generate and answer questions could inflate metrics
- Tests generalization: System should work with diverse query styles

### Why Self-Contained Services?
- **No app changes needed**: All modifications are in `validation/`
- **Safe experimentation**: Can break things without affecting production
- **Easy comparison**: Test multiple strategies side-by-side
- **Fast iteration**: Modify and test quickly

## Troubleshooting

### No logprobs returned
- Check that `intent_classification_model` in config is set to a model that supports logprobs
- Default: `openai/gpt-4o` (should work)

### All recall metrics are 0.0
- Check that `ground_truth_chunks` are populated in generated queries
- Verify that `chunk_id` is included in retrieved sources

### Query generation returns no questions
- Check LLM output in debug logs
- Verify PDF sources are downloaded (`prepare_sources.py`)
- Ensure `OPENROUTER_API_KEY` is set

## Tips

1. **Use CSV questions**: Export questions once, iterate on strategies without regenerating
2. **Incremental saves**: Results are saved every 5 queries, so you can resume if interrupted
3. **Parallel execution**: Use `--max-workers` to control parallelism (default: 4)
4. **Rate limiting**: Use `--rate-limit` to avoid overwhelming APIs
5. **RAGAS sampling**: Use `--ragas-sample-size` to limit RAGAS evaluation costs
