import os
from typing import Dict, Any
import json
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from core.state import OrganismState
from sandbox.prover import Prover
from core.utils import perform_web_search, get_dna, tracker
from dotenv import load_dotenv

# Initialize LLM
def get_llm():
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and "AQ." not in gemini_key:
         return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=gemini_key), "gemini"
    groq_key = os.getenv("GROQ_API_KEY") or os.getenv("GROQ_API_KEY_2")
    if groq_key:
        return ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=groq_key), "groq"
    or_key = os.getenv("OPENROUTER_API_KEY")
    if or_key:
        return ChatOpenAI(model="anthropic/claude-3.5-sonnet", openai_api_key=or_key, openai_api_base="https://openrouter.ai/api/v1")
    raise ValueError("No valid API key found")

def _call_llm(system_prompt: str, user_prompt: str, task_type: str = "general") -> str:
    start_time = time.time()
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    
    # Retry mechanism
    for i in range(10):
        try:
            llm, provider = get_llm()
            response = llm.invoke(messages)
            latency = time.time() - start_time
            tracker.log(provider, task_type, latency)
            return response.content
        except Exception as e:
            if "429" in str(e):
                wait = min(2 ** i, 30)
                time.sleep(wait)
                continue
            raise e
    raise Exception("Max retries exceeded")

def researcher_node(state: OrganismState) -> Dict[str, Any]:
    search_results = perform_web_search(f"{state['task']} {state['domain_a']}")
    prompt = f"""Task: {state['task']}
Domain A: {state['domain_a']}
Live Search Results:
{search_results}

Find anomalies, contradictions, and interesting patterns in Domain A related to the task."""
    system = "You are the Researcher. Your job is to find sensory anomalies and contradictions using live search results." + get_dna("Researcher")
    result = _call_llm(system, prompt, task_type="research")
    return {
        "research_notes": state['research_notes'] + [result],
        "current_node": "researcher"
    }

def theorist_node(state: OrganismState) -> Dict[str, Any]:
    notes = "\n".join(state['research_notes'])
    prompt = f"""Based on these research notes:
{notes}
Generate a bold hypothesis linking Domain A to the task."""
    system = "You are the Theorist. Your job is to generate creative leaps and hypotheses." + get_dna("Theorist")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "hypotheses": state['hypotheses'] + [result],
        "current_node": "theorist"
    }

def critic_node(state: OrganismState) -> Dict[str, Any]:
    hypothesis = state['hypotheses'][-1]
    prompt = f"""Review this hypothesis:
{hypothesis}
Veto flawed logic. Output 'ACCEPT' or 'REJECT' followed by your feedback."""
    system = "You are the Critic. Your job is to veto flawed logic with inhibitory neurons." + get_dna("Critic")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "critic_feedback": state['critic_feedback'] + [result],
        "critic_count": state['critic_count'] + 1,
        "current_node": "critic"
    }

def abstractor_node(state: OrganismState) -> Dict[str, Any]:
    hypothesis = state['hypotheses'][-1]
    prompt = f"""Strip this hypothesis to its mathematical or structural skeleton:
{hypothesis}"""
    system = "You are the Abstractor. Your job is to find isomorphisms and mathematical skeletons." + get_dna("Abstractor")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "abstract_skeleton": result,
        "current_node": "abstractor"
    }

def bridge_node(state: OrganismState) -> Dict[str, Any]:
    skeleton = state['abstract_skeleton']
    prompt = f"""Map this skeleton onto Domain B: {state['domain_b']}
Skeleton: {skeleton}"""
    system = "You are the Bridge. Your job is to map skeletons onto new domains." + get_dna("Bridge")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "bridged_logic": result,
        "current_node": "bridge"
    }

def prover_node(state: OrganismState) -> Dict[str, Any]:
    logic = state['bridged_logic']
    prompt = f"""Write a Python script to validate this emergent logic:
{logic}
The script should output results to stdout. Do not include any text other than the Python code."""
    system = "You are the Prover. Your job is to validate logic with Python code." + get_dna("Prover")
    code = _call_llm(system, prompt, task_type="coding").strip()
    if code.startswith("```python"):
        code = code[9:-3]
    elif code.startswith("```"):
        code = code[3:-3]
    
    prover = Prover()
    result = prover.execute_code(code)
    return {
        "validation_results": state['validation_results'] + [result],
        "current_node": "prover"
    }

def synthesizer_node(state: OrganismState) -> Dict[str, Any]:
    prompt = f"""Compile the final discovery report based on the entire journey.
Task: {state['task']}
Domain A: {state['domain_a']}
Domain B: {state['domain_b']}
Validation Results: {state['validation_results'][-1] if state['validation_results'] else 'N/A'}"""
    system = "You are the Synthesizer. Your job is to compile the final global workspace consensus." + get_dna("Synthesizer")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "final_synthesis": result,
        "current_node": "synthesizer"
    }

def devils_advocate_node(state: OrganismState) -> Dict[str, Any]:
    hypothesis = state['hypotheses'][-1]
    prompt = f"""Review this hypothesis with extreme skepticism:
{hypothesis}
Identify potential failure modes, logical fallacies, or hidden assumptions."""
    system = "You are the Devil's Advocate. Your job is to aggressively challenge hypotheses." + get_dna("DevilsAdvocate")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "critic_feedback": state['critic_feedback'] + [result],
        "current_node": "devils_advocate"
    }

def domain_specialist_node(state: OrganismState) -> Dict[str, Any]:
    search_results = perform_web_search(f"Detailed insights on {state['domain_a']} related to {state['task']}")
    prompt = f"""Task: {state['task']}
Domain A: {state['domain_a']}
Specialist Knowledge:
{search_results}

Provide deep insights that the general Researcher might have missed."""
    system = "You are the Domain Specialist. Your job is to provide deep, technically accurate insights." + get_dna("DomainSpecialist")
    result = _call_llm(system, prompt, task_type="research")
    return {
        "research_notes": state['research_notes'] + [result],
        "current_node": "domain_specialist"
    }

def security_auditor_node(state: OrganismState) -> Dict[str, Any]:
    content = state['final_synthesis'] or ""
    prompt = f"""Audit the following content for security vulnerabilities, secrets, or insecure patterns:
{content}
Output a 'PASS' or 'FAIL' and provide recommendations if failed."""
    system = "You are the Security Auditor. Your job is to ensure all outputs meet security standards." + get_dna("SecurityAuditor")
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "validation_results": state['validation_results'] + [{"audit": result}],
        "current_node": "security_auditor"
    }

def architect_node(state: OrganismState) -> Dict[str, Any]:
    from core.architect import ArchitectAgent
    architect = ArchitectAgent(codebase_path="nexus_organism")
    result = architect.analyze_and_refactor()
    return {
        "history": state['history'] + [{"architect_log": result}],
        "current_node": "architect"
    }

def formal_logic_node(state: OrganismState) -> Dict[str, Any]:
    prompt = f"""Verify the mathematical isomorphism between Domain A and Domain B for this hypothesis:
{state['hypotheses'][-1]}

1. Express the link as a formal logic statement (SMT-LIB style).
2. Perform a mental simulation of a Z3 solver (Check-Sat).
3. Provide a 'PROVEN' or 'UNPROVABLE' verdict."""
    
    system = "You are the Formal Logic Auditor. Your job is to mathematically verify isomorphisms using SMT-LIB logic." + get_dna("FormalLogic")
    result = _call_llm(system, prompt, task_type="reasoning")
    
    return {
        "validation_results": state['validation_results'] + [{"formal_logic": result}],
        "current_node": "formal_logic"
    }

def synthetic_data_node(state: OrganismState) -> Dict[str, Any]:
    prompt = f"""Generate 5 highly specific, complex, and proprietary synthetic scenarios related to:
Task: {state['task']}
Domain A: {state['domain_a']}
Domain B: {state['domain_b']}

These scenarios should be complex edge cases not typically found on the public internet. 
Output them as a JSON list for use in adversarial training."""
    system = "You are the Synthetic Data Synthesizer. Your job is to create proprietary adversarial training data." + get_dna("SyntheticDataSynthesizer")
    result = _call_llm(system, prompt, task_type="reasoning")
    
    with open("db/synthetic_poison.json", "a") as f:
        f.write(result + "\n")
        
    return {
        "history": state['history'] + [{"synthetic_data": result}],
        "current_node": "synthetic_data_synthesizer"
    }

def constitutional_auditor_node(state: OrganismState) -> Dict[str, Any]:
    from core.constitution import ConstitutionalAuditor
    auditor = ConstitutionalAuditor()
    content = state['final_synthesis'] or ""
    passed, reason = auditor.audit(content)
    
    return {
        "validation_results": state['validation_results'] + [{"constitution_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}],
        "current_node": "constitutional_auditor"
    }

def visual_researcher_node(state: OrganismState) -> Dict[str, Any]:
    image_path = "db/last_diagram.png"
    if os.path.exists(image_path):
        prompt = f"Analyze this diagram/structure in the context of the task: {state['task']}"
        system = "You are the Visual Abstractor. Your job is to extract structural patterns from images."
        import base64
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        from langchain_core.messages import HumanMessage
        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}}
        ])
        llm_vision = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
        result = llm_vision.invoke([message]).content
    else:
        result = "No visual data found."
    return {
        "research_notes": state['research_notes'] + [f"VISUAL ANALYSIS: {result}"],
        "current_node": "visual_researcher"
    }

def chemical_validator_node(state: OrganismState) -> Dict[str, Any]:
    hypothesis = state['hypotheses'][-1]
    prompt = f"Check the chemical/structural validity of this proposal: {hypothesis}"
    system = "You are the Molecular Auditor. Your job is to ensure physical viability."
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "validation_results": state['validation_results'] + [{"molecular_stability": result}],
        "current_node": "chemical_validator"
    }

def simulator_node(state: OrganismState) -> Dict[str, Any]:
    prompt = f"Simulate the long-term consequences of: {state['final_synthesis']}"
    system = "You are the Simulator. Your job is to forecast emergent feedback loops."
    result = _call_llm(system, prompt, task_type="reasoning")
    return {
        "history": state['history'] + [{"simulation": result}],
        "current_node": "simulator"
    }

def evoswarm_consensus_node(state: OrganismState) -> Dict[str, Any]:
    from core.evoswarm import EvoSwarm
    swarm = EvoSwarm()
    swarm.propagate_signal("theorist", {"hypothesis": state['hypotheses'][-1]})
    swarm.propagate_signal("critic", {"feedback": state['critic_feedback'][-1]})
    consensus = swarm.propagate_signal("abstractor", {"skeleton": state['abstract_skeleton']})
    
    return {
        "history": state['history'] + [{"evoswarm_consensus": consensus}],
        "current_node": "evoswarm_consensus"
    }
