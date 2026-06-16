import subprocess
import os

import subprocess
import os

class P2PSync:
    def __init__(self, repo_path):
        self.repo_path = repo_path

    def run_gossip(self):
        """Autonomous background sync loop."""
        try:
            print("🌐 P2P GOSSIP: Synchronizing state...")
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "add", "db/discovery_graph.gexf", "db/dna.json"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "commit", "-m", "Auto-gossip: Sync State"], cwd=self.repo_path, capture_output=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=self.repo_path, check=True)
            print("🌐 P2P GOSSIP: Synchronization complete.")
        except Exception as e:
            print(f"P2P Gossip failed: {e}")
