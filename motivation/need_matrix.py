from motivation.metabolism import Metabolism
import json
import os

class NeedMatrix:
    def __init__(self, state_file="db/needs.json"):
        self.state_file = state_file
        self.metabolism = Metabolism()
        self.curiosity_score = 0.5
        self.error_rate = 0.0
        self.compute_energy = 10
        self.load()

    def sync_metabolism(self):
        """Updates internal compute_energy based on physical device state."""
        state = self.metabolism.get_energy_state()
        self.compute_energy = state['energy']
        print(f"🔋 METABOLISM SYNC: Energy level established at {self.compute_energy} (Battery: {state['battery_level']}%)")

    def load(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.curiosity_score = data.get("curiosity_score", 0.5)
                    self.error_rate = data.get("error_rate", 0.0)
                    self.sync_metabolism()
            except Exception:
                pass

    def save(self):
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump({
                "curiosity_score": self.curiosity_score,
                "error_rate": self.error_rate,
                "compute_energy": self.compute_energy
            }, f)

    def update_on_novelty(self, amount=0.1):
        self.curiosity_score = min(1.0, self.curiosity_score + amount)
        self.compute_energy = max(0, self.compute_energy - 1)

    def update_on_boredom(self, amount=0.05):
        self.curiosity_score = max(0.0, self.curiosity_score - amount)

    def update_on_error(self):
        self.error_rate += 0.1
        self.compute_energy = max(0, self.compute_energy - 2)

    def reset_energy(self):
        self.compute_energy = 10
