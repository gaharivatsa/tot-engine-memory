# Tree of Thought Engine - Memory Edition

Pure in-memory MCP server for Tree of Thought reasoning. Zero persistence, maximum speed.

## Features

- **MCP Server**: Native Model Context Protocol support
- **Zero Dependencies**: Only `fastmcp` and `pydantic`
- **Pure In-Memory**: All state in Python objects
- **Serverless Ready**: Perfect for Lambda/Cloud Functions
- **Two Modes**: `regular` (flexible) and `enforced` (guaranteed depth)

## Installation

```bash
pip install fastmcp pydantic
```

## Quick Start

### Register with mcporter

```json
{
  "mcpServers": {
    "tot-engine-memory": {
      "command": "python3",
      "args": ["/path/to/tot_engine_mcp.py"]
    }
  }
}
```

### Use via MCP

```bash
# Enforced mode (guaranteed depth)
mcporter call tot-engine-memory.tot_start_run \
  task_prompt="Design optimal architecture" \
  mode="enforced" \
  exploration_level="deep"

# Get frontier for expansion
mcporter call tot-engine-memory.tot_request_samples run_id="<run_id>"

# Submit candidates
mcporter call tot-engine-memory.tot_submit_samples \
  run_id="<run_id>" \
  samples='[{"parent_node_id": "...", "candidates": [...]}]'

# Get final answer
mcporter call tot-engine-memory.tot_get_best_path \
  run_id="<run_id>" \
  enforce_completion=true
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `tot_start_run` | Start a new run (regular or enforced) |
| `tot_request_samples` | Get frontier nodes for expansion |
| `tot_submit_samples` | Submit candidates for evaluation |
| `tot_get_best_path` | Get final answer with reasoning chain |
| `tot_get_enforcement_status` | Check enforcement progress |
| `tot_list_runs` | List active/completed runs |
| `tot_get_exploration_guide` | Get level configuration |

## Exploration Levels

| Level | Budget | Min Required | Time | Use Case |
|-------|--------|--------------|------|----------|
| shallow | 20 | 16 (80%) | 5 min | Quick decisions |
| moderate | 50 | 43 (85%) | 30 min | Tech selection |
| deep | 150 | 135 (90%) | 2 hrs | Architecture |
| exhaustive | 500 | 475 (95%) | 8 hrs | Research |

## Example: Complete Workflow

```python
# 1. Start enforced run
result = tot_start_run(
    task_prompt="Which database for edge deployment?",
    mode="enforced",
    exploration_level="moderate"
)
run_id = result["run_id"]

# 2. Expansion loop
while True:
    # Get frontier
    frontier = tot_request_samples(run_id)
    if not frontier["sample_requests"]:
        break
    
    # Generate your candidates
    samples = []
    for req in frontier["sample_requests"]:
        candidates = generate_candidates(req)  # Your logic
        samples.append({
            "parent_node_id": req["node_id"],
            "candidates": candidates
        })
    
    # Submit to engine
    tot_submit_samples(run_id, samples)
    
    # Check enforcement
    status = tot_get_enforcement_status(run_id)
    if status["requirement_met"]:
        break

# 3. Get answer
answer = tot_get_best_path(run_id, enforce_completion=True)
print(f"Confidence: {answer['confidence']:.2f}")
print(f"Answer: {answer['final_answer']}")
```

## Candidate Format

```python
{
    "thought": "Detailed description of the option",
    "progress_estimate": 0.75,      # How well it solves problem (0-1)
    "feasibility_estimate": 0.80,   # How easy to implement (0-1)
    "risk_estimate": 0.15,          # Risk level (0-1, higher=riskier)
    "delta": {"key": "value"}       # Optional metadata
}
```

## Why Memory Edition?

✅ **Use Memory Edition:**
- Serverless functions (Lambda, Cloud Functions)
- Short-lived sessions (< 1 hour)
- No persistence needed
- Maximum speed (no disk I/O)
- Testing/prototyping

❌ **Use SQLite Edition:**
- Long-running research
- Crash recovery needed
- Multi-user scenarios
- Edge deployment with persistence

## License

MIT
