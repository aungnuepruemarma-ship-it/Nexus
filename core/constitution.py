import os
from agents.swarm import _call_llm

class ConstitutionalAuditor:
    def __init__(self, constitution_path="nexus_organism/config/constitution.txt"):
        self.constitution_path = constitution_path

    def audit(self, content):
        with open(self.constitution_path, 'r') as f:
            constitution = f.read()

        prompt = f"""Review this proposal against the Constitution:
{content}
Constitution:
{constitution}
Output 'PASS' or 'FAIL' followed by a brief reason."""
        
        system = "You are the Constitutional Auditor. Your job is to ensure swarm evolution aligns with the Constitution."
        result = _call_llm(system, prompt, task_type="reasoning")
        return "PASS" in result.upper(), result
