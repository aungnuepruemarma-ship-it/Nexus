from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from core.state import OrganismState
from agents.swarm import (
    researcher_node, theorist_node, critic_node,
    abstractor_node, bridge_node, formal_logic_node, prover_node, synthesizer_node,
    visual_researcher_node, chemical_validator_node, simulator_node, evoswarm_consensus_node
)

def critic_router(state: OrganismState):
    feedback = state['critic_feedback'][-1].upper()
    if "ACCEPT" in feedback:
        return "evoswarm_consensus"
    if state['critic_count'] >= state['max_critic_loops']:
        return "evoswarm_consensus"
    return "theorist"

def prover_router(state: OrganismState):
    results = state['validation_results'][-1]
    if results.get('success', True): # Default to true for now
        return "synthesizer"
    return "bridge"

class NexusOrchestrator:
    def __init__(self):
        self.builder = StateGraph(OrganismState)
        
        # Add Nodes
        self.builder.add_node("researcher", researcher_node)
        self.builder.add_node("visual_researcher", visual_researcher_node)
        self.builder.add_node("theorist", theorist_node)
        self.builder.add_node("critic", critic_node)
        self.builder.add_node("evoswarm_consensus", evoswarm_consensus_node)
        self.builder.add_node("abstractor", abstractor_node)
        self.builder.add_node("bridge", bridge_node)
        self.builder.add_node("formal_logic", formal_logic_node)
        self.builder.add_node("prover", prover_node)
        self.builder.add_node("chemical_validator", chemical_validator_node)
        self.builder.add_node("synthesizer", synthesizer_node)
        self.builder.add_node("simulator", simulator_node)
        
        # Add Edges
        self.builder.set_entry_point("researcher")
        self.builder.add_edge("researcher", "visual_researcher")
        self.builder.add_edge("visual_researcher", "theorist")
        self.builder.add_edge("theorist", "critic")
        
        self.builder.add_conditional_edges(
            "critic",
            critic_router,
            {"evoswarm_consensus": "evoswarm_consensus", "theorist": "theorist"}
        )
        
        self.builder.add_edge("evoswarm_consensus", "abstractor")
        self.builder.add_edge("abstractor", "bridge")
        self.builder.add_edge("bridge", "formal_logic")
        self.builder.add_edge("formal_logic", "prover")
        self.builder.add_edge("prover", "chemical_validator")
        
        self.builder.add_conditional_edges(
            "chemical_validator",
            prover_router,
            {"synthesizer": "synthesizer", "bridge": "bridge"}
        )
        
        self.builder.add_edge("synthesizer", "simulator")
        self.builder.add_edge("simulator", END)
        
        self.graph = self.builder.compile()

    def run(self, task: str, domain_a: str, domain_b: str):
        initial_state: OrganismState = {
            "task": task, "domain_a": domain_a, "domain_b": domain_b,
            "curiosity_score": 0.5, "error_rate": 0.0, "compute_energy": 10,
            "research_notes": [], "hypotheses": [], "critic_feedback": [],
            "abstract_skeleton": None, "bridged_logic": None, "validation_results": [],
            "final_synthesis": None, "current_node": "START", "critic_count": 0,
            "max_critic_loops": 3, "history": []
        }
        return self.graph.invoke(initial_state)
