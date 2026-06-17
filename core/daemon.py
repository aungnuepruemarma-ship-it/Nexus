import time
from core.orchestrator import NexusOrchestrator
from motivation.need_matrix import NeedMatrix
from evolution.self_evolution import SelfEvolution
from memory.discovery_graph import DiscoveryGraph
from core.architect import ArchitectAgent
from actions.git_agent import GitAgent
from motivation.metabolism import Metabolism

class NexusDaemon:
    def __init__(self):
        self.orchestrator = NexusOrchestrator()
        self.needs = NeedMatrix()
        self.evolution = SelfEvolution()
        self.graph = DiscoveryGraph()
        self.metabolism = Metabolism()
        self.git = GitAgent(repo_path=".")
        self.architect = ArchitectAgent(codebase_path="nexus_organism")

    def is_thermal_optimal(self):
        """Thermodynamic Gate: Only compute if within safe thermal envelope."""
        temp = self.metabolism.get_thermal_state()
        return temp < 50.0 # Strict thermal limit

    def tick(self):
        print(f"\n🧠 DAEMON TICK: curiosity={self.needs.curiosity_score:.2f}")
        
        if not self.is_thermal_optimal():
            print("🌡️ DAEMON: Thermal overload. Entering low-power contemplation mode.")
            time.sleep(10)
            return

        if self.needs.curiosity_score > 0.7:
            print("🚀 DAEMON: Curiosity threshold met. Initiating discovery...")
            task = "Find an interdisciplinary isomorphism"
            pair = ("Biology", "Computer Science")
            final_state = self.orchestrator.run(task, pair[0], pair[1])
            self.graph.add_discovery(pair[0], pair[1], final_state['final_synthesis'])
            
            # Auto-draft PR
            if final_state['final_synthesis']:
                self.git.draft_pr(f"discovery-{int(time.time())}", final_state['final_synthesis'], f"discovery_{int(time.time())}.md")
            
            # Auto-refactor
            self.architect.analyze_and_refactor()
            
            self.needs.update_on_novelty()
            self.evolution.apply_mutation(self.evolution.audit_run(final_state))
        else:
            self.needs.update_on_boredom()
        
        self.needs.save()
        self.evolution.genetic_audit()

    def start(self):
        print("🤖 DAEMON STARTED. Operating within thermodynamic constraints.")
        try:
            while True:
                self.tick()
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            print("🤖 DAEMON SHUTTING DOWN.")
