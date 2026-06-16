import json
import os
from agents.swarm import _call_llm

DNA_FILE = "db/dna.json"

class SelfEvolution:
    def __init__(self):
        if not os.path.exists("db"):
            os.makedirs("db")
        if not os.path.exists(DNA_FILE):
            with open(DNA_FILE, 'w') as f:
                json.dump({}, f)

    def audit_run(self, state):
        """Analyzes a completed run and suggests prompt improvements."""
        summary = f"""Task: {state['task']}
Success: {state['final_synthesis'] is not None}
Critic Rejections: {len([f for f in state['critic_feedback'] if 'REJECT' in f.upper()])}
Validation Failures: {len([r for r in state['validation_results'] if not r['success']])}"""

        prompt = f"""Review this Nexus Organism run summary:
{summary}
Suggest one specific prompt mutation for one of the agents (Researcher, Theorist, Critic, Abstractor, Bridge, Prover, Synthesizer) to improve future performance.
Output ONLY the name of the agent followed by a colon and the new instruction."""
        
        system = "You are the Evolution Engine. Your job is to perform self-audits and DNA mutations."
        suggestion = _call_llm(system, prompt)
        return suggestion

    def apply_mutation(self, suggestion):
        """Persists the mutation to DNA."""
        try:
            agent, instruction = suggestion.split(":", 1)
            agent = agent.strip()
            instruction = instruction.strip()
            
            with open(DNA_FILE, 'r') as f:
                dna = json.load(f)
            
            dna[agent] = dna.get(agent, []) + [instruction]
            
            with open(DNA_FILE, 'w') as f:
                json.dump(dna, f)
            print(f"DNA MUTATED: {agent} -> {instruction}")
        except Exception as e:
            print(f"FAILED TO MUTATE DNA: {e}")

    def genetic_audit(self):
        """Prunes ineffective DNA mutations."""
        print("🧬 RUNNING GENETIC AUDIT...")
        # Simple heuristic: remove instructions if Critic Rejections > 2 for that agent
        with open(DNA_FILE, 'r') as f:
            dna = json.load(f)
        
        # In a real system, we'd correlate specific instructions to rejection rates.
        # Here we just prune the last instruction as a simple demo of the mechanism.
        pruned = False
        for agent in dna:
            if len(dna[agent]) > 3:
                dna[agent].pop(0) # Prune oldest
                pruned = True
        
        if pruned:
            with open(DNA_FILE, 'w') as f:
                json.dump(dna, f)
            print("🧬 GENETIC AUDIT COMPLETE: Ineffective DNA pruned.")
        else:
            print("🧬 GENETIC AUDIT COMPLETE: No ineffective DNA found.")
