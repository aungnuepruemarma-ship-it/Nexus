import json
from agents.swarm import _call_llm

class PostmortemTool:
    def run_analysis(self, state):
        summary = f"Task: {state['task']}\nResult: {state['final_synthesis'] if state['final_synthesis'] else 'Failed'}"
        prompt = f"Analyze this run and output a 5-phase post-mortem (What happened, Root Cause, Impact, Lessons, Prevention) in JSON format.\n{summary}"
        return _call_llm("You are the Postmortem Engine.", prompt, task_type="reasoning")
