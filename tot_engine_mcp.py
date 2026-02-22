#!/usr/bin/env python3
"""
Tree of Thought Engine - MCP Server (Memory Edition)

Pure in-memory MCP server for Tree of Thought reasoning.
Zero dependencies beyond fastmcp and pydantic.

Test with:
    python3 tot_engine_mcp.py
    # Then test via mcporter or direct import
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from fastmcp import FastMCP

# MCP Server
mcp = FastMCP("tot-engine-memory")

# In-memory storage
runs: Dict[str, Any] = {}

# Enforcement configs
ENFORCEMENT_CONFIGS = {
    "shallow": {"node_budget": 20, "min_consumption_ratio": 0.80, "beam_width": 2, "n_generate": 2, "max_depth": 2, "target_score": 0.70},
    "moderate": {"node_budget": 50, "min_consumption_ratio": 0.85, "beam_width": 3, "n_generate": 3, "max_depth": 3, "target_score": 0.75},
    "deep": {"node_budget": 150, "min_consumption_ratio": 0.90, "beam_width": 5, "n_generate": 4, "max_depth": 5, "target_score": 0.80},
    "exhaustive": {"node_budget": 500, "min_consumption_ratio": 0.95, "beam_width": 7, "n_generate": 5, "max_depth": 8, "target_score": 0.85},
}

def calculate_score(progress: float, feasibility: float, risk: float) -> float:
    """Calculate composite score"""
    return 0.45 * progress + 0.35 * feasibility + 0.20 * (1 - risk) - 0.25 * risk

@mcp.tool()
def tot_start_run(
    task_prompt: str,
    mode: str = "regular",
    constraints: List[str] = None,
    beam_width: Optional[int] = None,
    n_generate: Optional[int] = None,
    max_depth: Optional[int] = None,
    node_budget: Optional[int] = None,
    target_score: Optional[float] = None,
    exploration_level: Optional[str] = None,
) -> Dict:
    """
    Start a ToT run (regular or enforced mode).
    
    Args:
        task_prompt: Problem to solve (required, min 5 chars)
        mode: "regular" (flexible) or "enforced" (guaranteed depth)
        constraints: List of hard constraints
        beam_width: Nodes to keep per iteration (1-10, regular mode)
        n_generate: Children per node (1-5, regular mode)
        max_depth: Max tree depth (1-20, regular mode)
        node_budget: Total node budget (2-1000, regular mode)
        target_score: Terminal threshold (0.0-1.0, regular mode)
        exploration_level: "shallow"/"moderate"/"deep"/"exhaustive" (enforced mode)
    
    Examples:
        Regular: tot_start_run("Which database?", "regular", beam_width=3)
        Enforced: tot_start_run("Design architecture", "enforced", exploration_level="deep")
    """
    constraints = constraints or []
    
    # Validate task_prompt length
    if len(task_prompt) < 5:
        return {"success": False, "error": "task_prompt must be at least 5 characters"}
    
    # Resolve config based on mode
    if mode == "enforced":
        if not exploration_level:
            return {"success": False, "error": "exploration_level required for enforced mode"}
        
        if exploration_level not in ENFORCEMENT_CONFIGS:
            return {"success": False, "error": f"Invalid exploration_level: {exploration_level}"}
        
        enf = ENFORCEMENT_CONFIGS[exploration_level]
        config = {
            "beam_width": beam_width if beam_width is not None else enf["beam_width"],
            "n_generate": n_generate if n_generate is not None else enf["n_generate"],
            "max_depth": max_depth if max_depth is not None else enf["max_depth"],
            "node_budget": node_budget if node_budget is not None else enf["node_budget"],
            "target_score": target_score if target_score is not None else enf["target_score"],
            "exploration_level": exploration_level,
            "min_required_nodes": int(enf["node_budget"] * enf["min_consumption_ratio"]),
        }
    else:  # regular mode
        config = {
            "beam_width": beam_width if beam_width is not None else 3,
            "n_generate": n_generate if n_generate is not None else 2,
            "max_depth": max_depth if max_depth is not None else 5,
            "node_budget": node_budget if node_budget is not None else 20,
            "target_score": target_score if target_score is not None else 0.85,
            "exploration_level": None,
            "min_required_nodes": 0,
        }
    
    run_id = str(uuid.uuid4())
    root_id = str(uuid.uuid4())
    
    runs[run_id] = {
        "run_id": run_id,
        "task_prompt": task_prompt,
        "mode": mode,
        "config": config,
        "constraints": constraints,
        "created_at": datetime.now().isoformat(),
        "status": "active",
        "nodes": {},
        "root_id": root_id,
    }
    
    # Create root node
    runs[run_id]["nodes"][root_id] = {
        "node_id": root_id,
        "parent_id": None,
        "depth": 0,
        "thought": f"ROOT: {task_prompt[:100]}",
        "score": 0.5,
        "status": "active",
        "delta": {},
    }
    
    response = {
        "success": True,
        "run_id": run_id,
        "root_node_id": root_id,
        "mode": mode,
        "config": config,
    }
    
    if mode == "enforced":
        response["enforcement"] = {
            "exploration_level": exploration_level,
            "min_required_nodes": config["min_required_nodes"],
            "message": f"MUST use {config['min_required_nodes']}+ nodes before synthesis",
        }
    
    return response

@mcp.tool()
def tot_request_samples(run_id: str) -> Dict:
    """Get frontier nodes for expansion"""
    if run_id not in runs:
        return {"success": False, "error": "Run not found"}
    
    run = runs[run_id]
    config = run["config"]
    
    # Find active nodes
    active = [n for n in run["nodes"].values() if n["status"] == "active"]
    if not active:
        return {"success": False, "error": "No frontier nodes to expand"}
    
    active.sort(key=lambda n: (-n["score"], n["depth"]))
    beam_width = config["beam_width"]
    frontier = active[:beam_width]
    
    response = {
        "success": True,
        "run_id": run_id,
        "mode": run["mode"],
        "frontier_size": len(frontier),
        "sample_requests": [
            {
                "node_id": n["node_id"],
                "depth": n["depth"],
                "thought": n["thought"],
                "score": n["score"],
                "num_candidates": config["n_generate"],
            }
            for n in frontier
        ],
    }
    
    if run["mode"] == "enforced":
        nodes_used = len(run["nodes"])
        min_required = config["min_required_nodes"]
        response["enforcement"] = {
            "nodes_used": nodes_used,
            "nodes_required": min_required,
            "requirement_met": nodes_used >= min_required,
        }
    
    return response

@mcp.tool()
def tot_submit_samples(run_id: str, samples: List[Dict]) -> Dict:
    """
    Submit candidates for evaluation.
    
    Args:
        run_id: The run ID
        samples: List of {parent_node_id, candidates[]} where candidates have:
            - thought: str
            - progress_estimate: float (0-1)
            - feasibility_estimate: float (0-1)
            - risk_estimate: float (0-1)
            - delta: dict (optional)
    """
    if run_id not in runs:
        return {"success": False, "error": "Run not found"}
    
    run = runs[run_id]
    config = run["config"]
    
    nodes_expanded = 0
    
    for sample in samples:
        parent_id = sample.get("parent_node_id")
        candidates = sample.get("candidates", [])
        
        if parent_id not in run["nodes"]:
            continue
        
        parent = run["nodes"][parent_id]
        
        if parent["depth"] >= config["max_depth"]:
            continue
        
        for cand in candidates:
            # Check budget
            if len(run["nodes"]) >= config["node_budget"]:
                return {
                    "success": True,
                    "status": "stopped",
                    "stop_reason": "budget_exhausted",
                    "nodes_expanded": nodes_expanded,
                }
            
            try:
                progress = float(cand.get("progress_estimate", 0.5))
                feasibility = float(cand.get("feasibility_estimate", 0.5))
                risk = float(cand.get("risk_estimate", 0.2))
                
                score = calculate_score(progress, feasibility, risk)
                status = "terminal" if score >= config["target_score"] else "active"
                
                node_id = str(uuid.uuid4())
                run["nodes"][node_id] = {
                    "node_id": node_id,
                    "parent_id": parent_id,
                    "depth": parent["depth"] + 1,
                    "thought": str(cand.get("thought", "")),
                    "score": score,
                    "status": status,
                    "delta": cand.get("delta", {}),
                }
                nodes_expanded += 1
            except Exception:
                continue
    
    return {
        "success": True,
        "nodes_expanded": nodes_expanded,
        "status": "running",
    }

@mcp.tool()
def tot_get_best_path(run_id: str, enforce_completion: bool = False) -> Dict:
    """
    Get best path and final answer.
    
    Args:
        run_id: The run ID
        enforce_completion: For enforced mode, require minimum nodes
    """
    if run_id not in runs:
        return {"success": False, "error": "Run not found"}
    
    run = runs[run_id]
    
    # Check enforcement
    if enforce_completion and run["mode"] == "enforced":
        nodes_used = len(run["nodes"])
        min_required = run["config"]["min_required_nodes"]
        
        if nodes_used < min_required:
            return {
                "success": False,
                "error": "Enforcement requirements not met",
                "nodes_used": nodes_used,
                "nodes_required": min_required,
                "message": f"Must use {min_required}+ nodes before synthesis. Continue expanding.",
            }
    
    if not run["nodes"]:
        return {"success": False, "error": "No nodes in run"}
    
    best = max(run["nodes"].values(), key=lambda n: (n["score"], n["depth"]))
    
    # Build path
    path = []
    current_id = best["node_id"]
    visited = set()
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = run["nodes"].get(current_id)
        if not node:
            break
        path.append({
            "node_id": node["node_id"],
            "depth": node["depth"],
            "thought": node["thought"],
            "score": node["score"],
        })
        current_id = node.get("parent_id")
    path.reverse()
    
    run["status"] = "completed"
    
    return {
        "success": True,
        "final_answer": best["thought"],
        "confidence": best["score"],
        "path_length": len(path),
        "mode": run["mode"],
        "reasoning_chain": path,
        "is_terminal": best["status"] == "terminal",
    }

@mcp.tool()
def tot_get_enforcement_status(run_id: str) -> Dict:
    """Get enforcement status for a run"""
    if run_id not in runs:
        return {"success": False, "error": "Run not found"}
    
    run = runs[run_id]
    nodes_used = len(run["nodes"])
    
    if run["mode"] != "enforced":
        return {
            "success": True,
            "mode": "regular",
            "nodes_used": nodes_used,
            "message": "Regular mode - no enforcement requirements",
        }
    
    min_required = run["config"]["min_required_nodes"]
    
    return {
        "success": True,
        "mode": "enforced",
        "level": run["config"].get("exploration_level"),
        "nodes_used": nodes_used,
        "nodes_required": min_required,
        "requirement_met": nodes_used >= min_required,
    }

@mcp.tool()
def tot_list_runs(limit: int = 10) -> Dict:
    """List recent runs"""
    run_list = sorted(runs.values(), key=lambda r: r["created_at"], reverse=True)[:limit]
    
    return {
        "success": True,
        "runs": [
            {
                "run_id": r["run_id"],
                "task_prompt": r["task_prompt"][:50] + "..." if len(r["task_prompt"]) > 50 else r["task_prompt"],
                "mode": r["mode"],
                "status": r["status"],
                "nodes": len(r["nodes"]),
            }
            for r in run_list
        ],
    }

@mcp.tool()
def tot_get_exploration_guide(level: str = "moderate") -> Dict:
    """
    Get exploration guide for a level.
    
    Args:
        level: "shallow", "moderate", "deep", or "exhaustive"
    """
    if level not in ENFORCEMENT_CONFIGS:
        return {"success": False, "error": f"Invalid level: {level}"}
    
    config = ENFORCEMENT_CONFIGS[level]
    
    descriptions = {
        "shallow": "Quick directional guidance (20 nodes, 80% min) - for simple decisions",
        "moderate": "Balanced exploration (50 nodes, 85% min) - for tech selection",
        "deep": "Thorough with validation (150 nodes, 90% min) - for architecture",
        "exhaustive": "Publication-grade research (500 nodes, 95% min) - for critical decisions",
    }
    
    return {
        "success": True,
        "level": level,
        "description": descriptions.get(level),
        "config": config,
        "min_required_nodes": int(config["node_budget"] * config["min_consumption_ratio"]),
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")
