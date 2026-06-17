from typing import TypedDict, List, Dict, Any, Optional
from pydantic import BaseModel

class OrganismState(TypedDict):
    task: str
    domain_a: str
    domain_b: str
    
    # Needs Matrix / Homeostasis
    curiosity_score: float
    error_rate: float
    compute_energy: int
    
    # Agent Memory / Output
    research_notes: List[str]
    hypotheses: List[str]
    critic_feedback: List[str]
    abstract_skeleton: Optional[str]
    bridged_logic: Optional[str]
    validation_results: List[Dict[str, Any]]
    final_synthesis: Optional[str]
    
    # Logic Gates (The State Machine)
    is_hypothesis_stable: bool
    is_logic_proven: bool
    is_security_passed: bool
    is_constitution_passed: bool
    
    # Control flow
    current_node: str
    critic_count: int
    max_critic_loops: int
    history: List[Dict[str, Any]]
