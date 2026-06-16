import subprocess
import os

class NomadSync:
    def __init__(self, repo_path):
        self.repo_path = repo_path

    def run_nomad_sync(self):
        """Hashes DB and DNA to IPFS for nomadic access."""
        try:
            print("🌌 NOMAD SYNC: Anchoring knowledge to IPFS...")
            # Add db directory to IPFS
            result = subprocess.run(["ipfs", "add", "-r", os.path.join(self.repo_path, "db")], 
                                    capture_output=True, text=True, check=True)
            cid = result.stdout.splitlines()[-1].split(" ")[1]
            print(f"🌌 NOMAD SYNC: Knowledge Anchored. CID: {cid}")
            return cid
        except Exception as e:
            print(f"Nomad Sync failed: {e}")
            return None
