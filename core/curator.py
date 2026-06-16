import os
from agents.swarm import _call_llm

class Curator:
    def __init__(self, codebase_path="nexus_organism"):
        self.codebase_path = codebase_path

    def generate_manual(self):
        """Compiles a system manual from codebase and DNA."""
        # Read codebase summary
        code_map = "nexus_organism/core/ \n nexus_organism/agents/ \n nexus_organism/memory/ \n nexus_organism/motivation/"
        
        # Read DNA
        dna_path = os.path.join(self.codebase_path, "db/dna.json")
        with open(dna_path, 'r') as f:
            dna = f.read()

        prompt = f"""Compile a System Manual for the Nexus Organism.
Codebase Structure: {code_map}
Current DNA: {dna}

Provide a concise overview for a new curator."""
        
        system = "You are the Curator. Your job is to document the Nexus Organism."
        manual = _call_llm(system, prompt, task_type="reasoning")
        
        with open("NEXUS_MANUAL.md", "w") as f:
            f.write(manual)
        return "Manual generated: NEXUS_MANUAL.md"
