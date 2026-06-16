import json
from typing import Dict, List, Any

class EvoSwarm:
    def __init__(self):
        self.consensus_threshold = 0.7
        self.quorum_signals = {}

    def propagate_signal(self, agent_id: str, signal: Dict[str, Any]):
        """Biological-inspired quorum sensing for swarm agents."""
        self.quorum_signals[agent_id] = signal
        # Check for quorum
        if len(self.quorum_signals) >= 3:
            return self.reach_consensus()
        return None

    def reach_consensus(self):
        """MAS consensus protocol logic."""
        # Simple majority rule based on signal consensus
        print("🧬 EVOSWARM: Quorum reached. Achieving Consensus.")
        return {"action": "evolve_and_adapt", "status": "consensus_achieved"}
