# Tree of Thought Engine - Memory Edition

Pure in-memory Tree of Thought reasoning. Zero dependencies. No persistence.

## Features

- **Zero Dependencies**: Only Python standard library
- **Pure In-Memory**: All state in Python objects
- **Serverless Ready**: Perfect for Lambda/Cloud Functions
- **Lightweight**: No database, no file I/O
- **Fast**: No disk operations

## Installation

```bash
pip install tot-engine-memory
```

## Quick Start

```python
from tot_engine_memory import TreeOfThought

tot = TreeOfThought()

# Start run (lost on restart!)
result = tot.start_run(
    mode="enforced",
    task_prompt="Which database?",
    exploration_level="moderate"
)

run_id = result["run_id"]

# Expand tree
while True:
    frontier = tot.request_samples(run_id)
    if not frontier["sample_requests"]:
        break
    
    candidates = generate_candidates(frontier)
    tot.submit_samples(run_id, candidates)

# Get answer
answer = tot.get_best_path(run_id)
print(f"Result: {answer['final_answer']}")
```

## When to Use

✅ **Use Memory Edition:**
- Serverless functions (Lambda, Cloud Functions)
- Short-lived sessions (< 1 hour)
- No persistence needed
- Testing/prototyping

❌ **Use SQLite Edition:**
- Long-running research
- Crash recovery needed
- Edge deployment (Pi 4)
- Multiple users

## API

Same API as SQLite edition:
- `start_run(mode, task_prompt, ...)`
- `request_samples(run_id)`
- `submit_samples(run_id, samples)`
- `get_best_path(run_id)`

## License

MIT
