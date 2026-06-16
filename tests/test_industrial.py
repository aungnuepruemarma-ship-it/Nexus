from agents.swarm import synthetic_data_node
from core.state import OrganismState
import json
import os

# Create a mock state for the test
mock_state: OrganismState = {
    "task": "Test Synthetic Data Node",
    "domain_a": "Cryptography",
    "domain_b": "Quantum Computing",
    "research_notes": [],
    "hypotheses": [],
    "critic_feedback": [],
    "abstract_skeleton": None,
    "bridged_logic": None,
    "validation_results": [],
    "final_synthesis": None,
    "current_node": "START",
    "critic_count": 0,
    "max_critic_loops": 3,
    "history": [],
    "curiosity_score": 0.5,
    "error_rate": 0.0,
    "compute_energy": 10
}

print("🧪 Testing SyntheticDataSynthesizer...")
try:
    result = synthetic_data_node(mock_state)
    print("✅ SyntheticDataSynthesizer Success!")
    if os.path.exists("db/synthetic_poison.json"):
        with open("db/synthetic_poison.json", "r") as f:
            print("Contents of db/synthetic_poison.json:")
            print(f.read()[-500:]) # Print last 500 chars
except Exception as e:
    print(f"❌ Test Failed: {e}")
