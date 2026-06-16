import time
import random
from apscheduler.schedulers.background import BackgroundScheduler
from core.orchestrator import NexusOrchestrator
from motivation.need_matrix import NeedMatrix
from evolution.self_evolution import SelfEvolution
from memory.discovery_graph import DiscoveryGraph
from core.architect import ArchitectAgent
from actions.git_agent import GitAgent

class NexusDaemon:
    def __init__(self):
        self.orchestrator = NexusOrchestrator()
        self.needs = NeedMatrix()
        self.evolution = SelfEvolution()
        self.graph = DiscoveryGraph()
        self.scheduler = BackgroundScheduler()
        self.git = GitAgent(repo_path=".")
        self.architect = ArchitectAgent(codebase_path="nexus_organism")

    def tick(self):
        print(f"\n🧠 DAEMON TICK: curiosity={self.needs.curiosity_score:.2f}")
        if self.needs.curiosity_score > 0.7:
            print("🚀 DAEMON: Curiosity threshold met. Initiating discovery...")
            # Pick a random discovery task
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
        self.scheduler.add_job(self.tick, 'interval', seconds=60)
        self.scheduler.start()
        print("🤖 DAEMON STARTED. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            self.scheduler.shutdown()
