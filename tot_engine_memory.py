#!/usr/bin/env python3
"""
Tree of Thought Engine v3.0 - Pure In-Memory Implementation

Lightweight, generic ToT engine with no external dependencies.
All state stored in Python dictionaries - runs vanish on restart.

Usage:
    from server_memory import TreeOfThought
    
    tot = TreeOfThought()
    
    # Start run
    run = tot.start_run(
        mode="enforced",
        task_prompt="Design optimal architecture",
        exploration_level="deep"
    )
    
    # Interactive expansion loop
    while True:
        frontier = tot.request_samples(run["run_id"])
        if not frontier["sample_requests"]:
            break
        
        # Generate candidates (your logic here)
        candidates = generate_candidates(frontier)
        
        tot.submit_samples(run["run_id"], candidates)
    
    # Get result
    result = tot.get_best_path(run["run_id"])
"""

import uuid
import hashlib
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Import enforcement and config
from enforcement import get_enforcement_config, calculate_score
from config import get_depth_guideline, DEPTH_CONFIGS


@dataclass
class Node:
    """Tree node representing a reasoning step"""
    node_id: str
    run_id: str
    parent_id: Optional[str]
    depth: int
    thought: str
    score: float
    status: str = "active"  # active, terminal, pruned
    delta: Dict = field(default_factory=dict)
    evaluation: Dict = field(default_factory=dict)
    children: List[str] = field(default_factory=list)


@dataclass  
class Run:
    """Research session"""
    run_id: str
    task_prompt: str
    mode: str  # "regular" or "enforced"
    config: Dict[str, Any]
    constraints: List[str]
    created_at: str
    status: str = "active"
    best_node_id: Optional[str] = None
    nodes: Dict[str, Node] = field(default_factory=dict)
    root_id: Optional[str] = None


class TreeOfThought:
    """
    Pure in-memory Tree of Thought engine.
    
    No external dependencies. All data stored in Python objects.
    Runs are lost when the instance is destroyed.
    """
    
    def __init__(self):
        self.runs: Dict[str, Run] = {}
        self._stats = {"total_runs": 0, "total_nodes": 0}
    
    def start_run(
        self,
        task_prompt: str,
        mode: str = "regular",
        constraints: List[str] = None,
        # Regular params
        beam_width: Optional[int] = None,
        n_generate: Optional[int] = None,
        max_depth: Optional[int] = None,
        node_budget: Optional[int] = None,
        target_score: Optional[float] = None,
        # Enforced params
        exploration_level: Optional[str] = None,
        # Override for enforced
        custom_beam_width: Optional[int] = None,
        custom_target_score: Optional[float] = None,
    ) -> Dict:
        """
        Start a new ToT run.
        
        Args:
            task_prompt: The problem to solve
            mode: "regular" (flexible) or "enforced" (guaranteed depth)
            constraints: Hard constraints
            
            # Regular mode - set these directly
            beam_width, n_generate, max_depth, node_budget, target_score
            
            # Enforced mode - use preset
            exploration_level: "shallow" | "moderate" | "deep" | "exhaustive"
            custom_beam_width: Optional override
            custom_target_score: Optional override
        """
        constraints = constraints or []
        
        # Resolve config based on mode
        if mode == "enforced":
            if not exploration_level:
                raise ValueError("exploration_level required when mode='enforced'")
            
            enf = get_enforcement_config(exploration_level)
            config = {
                "beam_width": custom_beam_width or enf.beam_width,
                "n_generate": enf.n_generate,
                "max_depth": enf.max_depth,
                "node_budget": enf.node_budget,
                "target_score": custom_target_score or enf.target_score,
                "exploration_level": exploration_level,
                "min_required_nodes": enf.min_required_nodes,
            }
        else:
            config = {
                "beam_width": beam_width or 3,
                "n_generate": n_generate or 2,
                "max_depth": max_depth or 5,
                "node_budget": node_budget or 20,
                "target_score": target_score or 0.85,
                "exploration_level": None,
                "min_required_nodes": 0,
            }
        
        # Create run
        run_id = str(uuid.uuid4())
        run = Run(
            run_id=run_id,
            task_prompt=task_prompt,
            mode=mode,
            config=config,
            constraints=constraints,
            created_at=datetime.now().isoformat(),
        )
        
        # Create root node
        root_id = str(uuid.uuid4())
        root = Node(
            node_id=root_id,
            run_id=run_id,
            parent_id=None,
            depth=0,
            thought=f"ROOT: {task_prompt[:100]}",
            score=0.5,
            status="active",
            delta={"constraints": constraints},
        )
        
        run.nodes[root_id] = root
        run.root_id = root_id
        self.runs[run_id] = run
        self._stats["total_runs"] += 1
        self._stats["total_nodes"] += 1
        
        # Build response
        response = {
            "success": True,
            "run_id": run_id,
            "root_node_id": root_id,
            "mode": mode,
            "config": config,
        }
        
        if mode == "enforced":
            guideline = get_depth_guideline(0)
            response["enforcement"] = {
                "exploration_level": exploration_level,
                "min_required_nodes": config["min_required_nodes"],
                "message": f"MUST use {config['min_required_nodes']}+ nodes",
            }
            response["scoring_guideline"] = {
                "depth_0_range": guideline.score_range,
                "strategy": guideline.strategy,
            }
        
        return response
    
    def request_samples(self, run_id: str) -> Dict:
        """Get frontier nodes for expansion"""
        if run_id not in self.runs:
            return {"success": False, "error": "Run not found"}
        
        run = self.runs[run_id]
        config = run.config
        
        # Find active nodes, sort by score
        active_nodes = [
            n for n in run.nodes.values()
            if n.status == "active"
        ]
        
        if not active_nodes:
            return {"success": False, "error": "No frontier nodes"}
        
        active_nodes.sort(key=lambda n: (-n.score, n.depth))
        frontier = active_nodes[:config["beam_width"]]
        
        response = {
            "success": True,
            "run_id": run_id,
            "mode": run.mode,
            "frontier_size": len(frontier),
            "sample_requests": [
                {
                    "node_id": n.node_id,
                    "depth": n.depth,
                    "thought": n.thought,
                    "score": n.score,
                    "num_candidates": config["n_generate"],
                }
                for n in frontier
            ],
        }
        
        # Add enforcement guidance
        if run.mode == "enforced":
            level = run.config.get("exploration_level")
            if level:
                enf = get_enforcement_config(level)
                guideline = get_depth_guideline(frontier[0].depth)
                
                nodes_used = len(run.nodes)
                min_required = enf.min_required_nodes
                
                response["enforcement"] = {
                    "level": level,
                    "nodes_used": nodes_used,
                    "nodes_required": min_required,
                    "requirement_met": nodes_used >= min_required,
                    "scoring_range": guideline.score_range,
                    "strategy": guideline.strategy,
                }
        
        return response
    
    def submit_samples(self, run_id: str, samples: List[Dict]) -> Dict:
        """Submit candidates for evaluation and insertion"""
        if run_id not in self.runs:
            return {"success": False, "error": "Run not found"}
        
        run = self.runs[run_id]
        config = run.config
        level = run.config.get("exploration_level", "moderate")
        
        nodes_expanded = 0
        nodes_pruned = 0
        
        for sample in samples:
            parent_id = sample.get("parent_node_id")
            candidates = sample.get("candidates", [])
            
            if parent_id not in run.nodes:
                continue
            
            parent = run.nodes[parent_id]
            
            if parent.depth >= config["max_depth"]:
                continue
            
            for cand_data in candidates:
                # Check budget
                if len(run.nodes) >= config["node_budget"]:
                    return {
                        "success": True,
                        "status": "stopped",
                        "stop_reason": "budget_exhausted",
                        "nodes_expanded": nodes_expanded,
                    }
                
                try:
                    # Calculate score
                    progress = cand_data.get("progress_estimate", 0.5)
                    feasibility = cand_data.get("feasibility_estimate", 0.5)
                    risk = cand_data.get("risk_estimate", 0.2)
                    
                    score = calculate_score(progress, feasibility, 0.7, risk, level)
                    
                    # Determine status
                    status = "terminal" if score >= config["target_score"] else "active"
                    
                    # Create node
                    node_id = str(uuid.uuid4())
                    node = Node(
                        node_id=node_id,
                        run_id=run_id,
                        parent_id=parent_id,
                        depth=parent.depth + 1,
                        thought=cand_data["thought"],
                        score=score,
                        status=status,
                        delta=cand_data.get("delta", {}),
                        evaluation={
                            "progress": progress,
                            "feasibility": feasibility,
                            "risk": risk,
                            "reasoning": cand_data.get("reasoning", ""),
                        },
                    )
                    
                    run.nodes[node_id] = node
                    parent.children.append(node_id)
                    nodes_expanded += 1
                    self._stats["total_nodes"] += 1
                    
                except Exception as e:
                    nodes_pruned += 1
        
        return {
            "success": True,
            "nodes_expanded": nodes_expanded,
            "nodes_pruned": nodes_pruned,
            "status": "running",
        }
    
    def get_best_path(self, run_id: str, enforce_completion: bool = False) -> Dict:
        """Get best path and final answer"""
        if run_id not in self.runs:
            return {"success": False, "error": "Run not found"}
        
        run = self.runs[run_id]
        
        # Check enforcement
        if enforce_completion and run.mode == "enforced":
            nodes_used = len(run.nodes)
            min_required = run.config.get("min_required_nodes", 0)
            
            if nodes_used < min_required:
                return {
                    "success": False,
                    "error": "Enforcement requirements not met",
                    "nodes_used": nodes_used,
                    "nodes_required": min_required,
                    "message": f"Must use {min_required}+ nodes",
                }
        
        # Find best node
        if not run.nodes:
            return {"success": False, "error": "No nodes"}
        
        best = max(run.nodes.values(), key=lambda n: (n.score, n.depth))
        
        # Build path
        path = []
        current = best
        while current:
            path.append({
                "node_id": current.node_id,
                "depth": current.depth,
                "thought": current.thought,
                "score": current.score,
            })
            if current.parent_id and current.parent_id in run.nodes:
                current = run.nodes[current.parent_id]
            else:
                break
        path.reverse()
        
        run.status = "completed"
        run.best_node_id = best.node_id
        
        return {
            "success": True,
            "final_answer": best.thought,
            "confidence": best.score,
            "path_length": len(path),
            "mode": run.mode,
            "reasoning_chain": path,
            "is_terminal": best.status == "terminal",
        }
    
    def get_enforcement_status(self, run_id: str) -> Dict:
        """Get enforcement status for a run"""
        if run_id not in self.runs:
            return {"success": False, "error": "Run not found"}
        
        run = self.runs[run_id]
        nodes_used = len(run.nodes)
        
        if run.mode != "enforced":
            return {
                "success": True,
                "mode": "regular",
                "nodes_used": nodes_used,
                "message": "Regular mode - no enforcement",
            }
        
        min_required = run.config.get("min_required_nodes", 0)
        max_depth = max((n.depth for n in run.nodes.values()), default=0)
        
        return {
            "success": True,
            "mode": "enforced",
            "level": run.config.get("exploration_level"),
            "nodes_used": nodes_used,
            "nodes_required": min_required,
            "requirement_met": nodes_used >= min_required,
            "max_depth": max_depth,
        }
    
    def get_exploration_guide(self, level: str = "moderate") -> Dict:
        """Get exploration guide"""
        config = DEPTH_CONFIGS[level]
        guideline = get_depth_guideline(0)
        
        return {
            "success": True,
            "level": level,
            "config": config,
            "scoring": {
                "range": guideline.score_range,
                "strategy": guideline.strategy,
            },
        }
    
    def list_runs(self, limit: int = 10) -> Dict:
        """List recent runs"""
        runs = list(self.runs.values())
        runs.sort(key=lambda r: r.created_at, reverse=True)
        
        return {
            "success": True,
            "runs": [
                {
                    "run_id": r.run_id,
                    "task_prompt": r.task_prompt[:50] + "...",
                    "mode": r.mode,
                    "status": r.status,
                    "created_at": r.created_at,
                    "nodes": len(r.nodes),
                }
                for r in runs[:limit]
            ],
        }
    
    def get_stats(self) -> Dict:
        """Get engine statistics"""
        return {
            "total_runs": self._stats["total_runs"],
            "total_nodes": self._stats["total_nodes"],
            "active_runs": len([r for r in self.runs.values() if r.status == "active"]),
            "completed_runs": len([r for r in self.runs.values() if r.status == "completed"]),
        }
    
    def delete_run(self, run_id: str) -> bool:
        """Delete a run and free memory"""
        if run_id in self.runs:
            run = self.runs.pop(run_id)
            self._stats["total_nodes"] -= len(run.nodes)
            return True
        return False


# ============================================================================
# Example Usage
# ============================================================================

def example():
    """Example of using the in-memory ToT engine"""
    
    tot = TreeOfThought()
    
    # Start enforced run
    result = tot.start_run(
        mode="enforced",
        task_prompt="Which database for edge deployment?",
        exploration_level="moderate",
        constraints=["Pi 4 compatible", "Self-hosted"],
    )
    
    run_id = result["run_id"]
    print(f"Started run: {run_id}")
    
    # Expansion loop
    for iteration in range(10):
        frontier = tot.request_samples(run_id)
        if not frontier.get("sample_requests"):
            break
        
        samples = []
        for req in frontier["sample_requests"]:
            # Generate candidates (simplified)
            candidates = [
                {
                    "thought": f"Option A for {req['thought'][:30]}...",
                    "progress_estimate": 0.7,
                    "feasibility_estimate": 0.8,
                    "risk_estimate": 0.2,
                    "reasoning": "Good fit",
                    "delta": {"option": "A"},
                },
                {
                    "thought": f"Option B for {req['thought'][:30]}...",
                    "progress_estimate": 0.6,
                    "feasibility_estimate": 0.9,
                    "risk_estimate": 0.1,
                    "reasoning": "Safer choice",
                    "delta": {"option": "B"},
                },
            ]
            samples.append({
                "parent_node_id": req["node_id"],
                "candidates": candidates,
            })
        
        result = tot.submit_samples(run_id, samples)
        print(f"Iteration {iteration + 1}: {result['nodes_expanded']} nodes")
        
        # Check enforcement
        status = tot.get_enforcement_status(run_id)
        if status.get("requirement_met"):
            print("Enforcement requirements met!")
    
    # Get final answer
    final = tot.get_best_path(run_id, enforce_completion=True)
    print(f"\nFinal answer: {final['final_answer']}")
    print(f"Confidence: {final['confidence']:.2f}")
    
    # Stats
    print(f"\nStats: {tot.get_stats()}")


if __name__ == "__main__":
    example()
