import os
import json
from agents.swarm import _call_llm
from sandbox.prover import Prover
from core.verification import VerificationEngine

class ArchitectAgent:
    def __init__(self, codebase_path):
        self.codebase_path = codebase_path
        self.verifier = VerificationEngine(codebase_path)

    def analyze_and_refactor(self):
        """Analyzes own codebase to suggest structural improvements."""
        # Read codebase (limited to core/ and agents/)
        code_map = ""
        for root, _, files in os.walk(os.path.join(self.codebase_path, "core")):
            for file in files:
                with open(os.path.join(root, file), 'r') as f:
                    code_map += f"File: {file}\n{f.read()}\n\n"

        prompt = f"""Analyze this codebase and propose one structural refactoring to improve modularity or performance:
{code_map}
Output ONLY the file path to change and the new code in a JSON format."""
        
        system = "You are the Architect. Your job is to improve the organism's own structural integrity."
        suggestion = _call_llm(system, prompt)
        
        # Validation with VerificationEngine
        try:
            data = json.loads(suggestion)
            if self.verifier.verify_refactor(data['path'], data['code']):
                return f"Self-refactored {data['path']} successfully."
            else:
                return f"Refactoring of {data['path']} failed verification."
        except Exception as e:
            return f"Architect failed: {e}"
