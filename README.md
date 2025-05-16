# Travel Planning System Evaluation

This directory contains tools and data for evaluating the travel planning system.

## Directory Structure

- `eval.json` - Main evaluation data file containing test cases and results
- `eval.py` - Core evaluation script
- `collect_evaluation_data.py` - Script to collect evaluation data from the travel planning system
- `llm_judge.py` - Script to evaluate travel plans using multiple LLMs
- `analyze_evaluations.py` - Script to analyze evaluation results and generate statistics
- `analysis/` - Directory containing evaluation analysis results
  - `score_distribution.png` - Histogram of evaluation scores by model
  - `case_statistics.csv` - Statistics for each evaluation case
  - `model_statistics.csv` - Statistics for each evaluation model
  - `overall_statistics.txt` - Overall evaluation statistics
- `evaluation_collection.log` - Log file for data collection process
- `llm_evaluation.log` - Log file for LLM evaluation process

## Evaluation Workflow

The evaluation process consists of three main steps:

1. **Data Collection** (`collect_evaluation_data.py`):
   - Processes user requests through the travel planning system
   - Collects recommendations, itineraries, and budgets
   - Saves results to the evaluation JSON file

2. **LLM Evaluation** (`llm_judge.py`):
   - Evaluates travel plans using multiple LLM models
   - Assigns scores and provides justifications
   - Updates the evaluation JSON file with results

3. **Analysis** (`analyze_evaluations.py`):
   - Extracts scores from the evaluation data
   - Generates histograms and statistics
   - Saves results to the analysis directory

## Usage

See the individual README files for detailed instructions:

- [Data Collection README](README_evaluation.md)
- [LLM Evaluation README](README_llm_judge.md)
- [Analysis README](README_analysis.md)

## Quick Start

To run the complete evaluation pipeline:

1. Collect evaluation data:
   ```bash
   python collect_evaluation_data.py
   ```

2. Evaluate using LLM models:
   ```bash
   python llm_judge.py --api-key YOUR_API_KEY
   ```

3. Analyze results:
   ```bash
   python analyze_evaluations.py
   ```

All commands should be run from within the `evaluation` directory. 