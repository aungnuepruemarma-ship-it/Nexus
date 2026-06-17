from core.orchestrator import NexusOrchestrator
from core.state import OrganismState

print("🧠 TESTING ONTOLOGICAL ENGINE...")
orchestrator = NexusOrchestrator()

# Minimal tournament to test new ontological nodes
try:
    result = orchestrator.run(
        task="Test Ontological Convergence",
        domain_a="Topology",
        domain_b="Logic"
    )
    
    # Verify the new nodes were reached
    history_nodes = [step.get('current_node') for step in result['history'] if 'current_node' in step]
    print(f"✅ Tournament Reached Nodes: {history_nodes}")
    
    if result['final_synthesis']:
        print("✅ Synthesis Success.")
    
except Exception as e:
    print(f"❌ Test Failed: {e}")
