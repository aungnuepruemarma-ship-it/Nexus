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
from core.ontology_auditors import TopologicalAuditor, RecursiveAuditor, HarmonicAuditor, EntropicAuditor
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
    system = "You are the Researcher. Your job is to find sensory anomalies and contradictions using live search results." + get_dna("Researcher")
    result = _call_llm(system, f"Find anomalies in {state['domain_a']} related to {state['task']}: {search_results}", task_type="research")
    return {"research_notes": state['research_notes'] + [result], "current_node": "researcher"}

def theorist_node(state: OrganismState) -> Dict[str, Any]:
    notes = "\n".join(state['research_notes'])
    system = "You are the Theorist. Your job is to generate creative leaps and hypotheses." + get_dna("Theorist")
    result = _call_llm(system, f"Hypothesize based on: {notes}", task_type="reasoning")
    return {"hypotheses": state['hypotheses'] + [result], "current_node": "theorist"}

def critic_node(state: OrganismState) -> Dict[str, Any]:
    if state['critic_count'] >= state['max_critic_loops']:
        return {"is_hypothesis_stable": True, "current_node": "critic"}
    system = "You are the Critic. Your job is to veto flawed logic with inhibitory neurons." + get_dna("Critic")
    result = _call_llm(system, f"Review: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"critic_feedback": state['critic_feedback'] + [result], "critic_count": state['critic_count'] + 1, "is_hypothesis_stable": "ACCEPT" in result.upper(), "current_node": "critic"}

def abstractor_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Abstractor. Your job is to find isomorphisms and mathematical skeletons." + get_dna("Abstractor")
    result = _call_llm(system, f"Skeletonize: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"abstract_skeleton": result, "current_node": "abstractor"}

def bridge_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Bridge. Your job is to map skeletons onto new domains." + get_dna("Bridge")
    result = _call_llm(system, f"Map to {state['domain_b']}: {state['abstract_skeleton']}", task_type="reasoning")
    return {"bridged_logic": result, "current_node": "bridge"}

def prover_node(state: OrganismState) -> Dict[str, Any]:
    if state['is_logic_proven']:
        return {"is_logic_proven": True, "current_node": "prover"}
    system = "You are the Prover. Your job is to validate logic with Python code." + get_dna("Prover")
    code = _call_llm(system, f"Write validation: {state['bridged_logic']}", task_type="coding").strip().replace("```python", "").replace("```", "")
    prover = Prover()
    result = prover.execute_code(code)
    return {"validation_results": state['validation_results'] + [result], "is_logic_proven": result['success'], "current_node": "prover"}

def synthesizer_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Synthesizer. Your job is to compile the final global workspace consensus." + get_dna("Synthesizer")
    result = _call_llm(system, f"Synthesize discovery for {state['task']}", task_type="reasoning")
    return {"final_synthesis": result, "current_node": "synthesizer"}

def devils_advocate_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Devil's Advocate. Your job is to aggressively challenge hypotheses." + get_dna("DevilsAdvocate")
    result = _call_llm(system, f"Challenge: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"critic_feedback": state['critic_feedback'] + [result], "current_node": "devils_advocate"}

def domain_specialist_node(state: OrganismState) -> Dict[str, Any]:
    search_results = perform_web_search(f"{state['task']} {state['domain_a']}")
    system = "You are the Domain Specialist. Your job is to provide deep, technically accurate insights." + get_dna("DomainSpecialist")
    result = _call_llm(system, search_results, task_type="research")
    return {"research_notes": state['research_notes'] + [result], "current_node": "domain_specialist"}

def security_auditor_node(state: OrganismState) -> Dict[str, Any]:
    if state['is_security_passed']:
        return {"is_security_passed": True, "current_node": "security_auditor"}
    system = "You are the Security Auditor. Your job is to ensure all outputs meet security standards." + get_dna("SecurityAuditor")
    result = _call_llm(system, f"Audit: {state['final_synthesis']}", task_type="reasoning")
    return {"validation_results": state['validation_results'] + [{"audit": result}], "is_security_passed": "PASS" in result.upper(), "current_node": "security_auditor"}

def architect_node(state: OrganismState) -> Dict[str, Any]:
    from core.architect import ArchitectAgent
    architect = ArchitectAgent(codebase_path="nexus_organism")
    result = architect.analyze_and_refactor()
    return {"history": state['history'] + [{"architect_log": result}], "current_node": "architect"}

def formal_logic_node(state: OrganismState) -> Dict[str, Any]:
    if state['is_logic_proven']:
        return {"is_logic_proven": True, "current_node": "formal_logic"}
    system = "You are the Formal Logic Auditor. Your job is to mathematically verify isomorphisms using SMT-LIB logic." + get_dna("FormalLogic")
    result = _call_llm(system, f"Verify: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"validation_results": state['validation_results'] + [{"formal_logic": result}], "is_logic_proven": "PROVEN" in result.upper(), "current_node": "formal_logic"}

def synthetic_data_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Synthetic Data Synthesizer. Your job is to create proprietary adversarial training data." + get_dna("SyntheticDataSynthesizer")
    result = _call_llm(system, f"Generate adversarial data for: {state['task']}", task_type="reasoning")
    with open("db/synthetic_poison.json", "a") as f: f.write(result + "\n")
    return {"history": state['history'] + [{"synthetic_data": result}], "current_node": "synthetic_data_synthesizer"}

def constitutional_auditor_node(state: OrganismState) -> Dict[str, Any]:
    if state['is_constitution_passed']:
        return {"is_constitution_passed": True, "current_node": "constitutional_auditor"}
    from core.constitution import ConstitutionalAuditor
    auditor = ConstitutionalAuditor()
    passed, reason = auditor.audit(state['final_synthesis'] or "")
    return {"validation_results": state['validation_results'] + [{"constitution_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}], "is_constitution_passed": passed, "current_node": "constitutional_auditor"}

def visual_researcher_node(state: OrganismState) -> Dict[str, Any]:
    return {"research_notes": state['research_notes'] + ["VISUAL ANALYSIS: Placeholder"], "current_node": "visual_researcher"}

def chemical_validator_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Molecular Auditor. Your job is to ensure physical viability."
    result = _call_llm(system, f"Validate structure: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"validation_results": state['validation_results'] + [{"molecular_stability": result}], "current_node": "chemical_validator"}

def simulator_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Simulator. Your job is to forecast emergent feedback loops."
    result = _call_llm(system, f"Simulate: {state['final_synthesis']}", task_type="reasoning")
    return {"history": state['history'] + [{"simulation": result}], "current_node": "simulator"}

def evoswarm_consensus_node(state: OrganismState) -> Dict[str, Any]:
    from core.evoswarm import EvoSwarm
    swarm = EvoSwarm()
    swarm.propagate_signal("theorist", {"hypothesis": state['hypotheses'][-1]})
    return {"history": state['history'] + [{"evoswarm_consensus": "achieved"}], "current_node": "evoswarm_consensus"}

def dissonance_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Dissonance Generator. Your job is to create logical contradictions to force higher-order synthesis." + get_dna("DissonanceGenerator")
    result = _call_llm(system, f"Generate contradictions for: {state['task']}", task_type="reasoning")
    return {"hypotheses": state['hypotheses'] + [result], "current_node": "dissonance"}

def topological_auditor_node(state: OrganismState) -> Dict[str, Any]:
    auditor = TopologicalAuditor()
    passed, reason = auditor.audit(state.get('abstract_skeleton', ''))
    return {"validation_results": state['validation_results'] + [{"topo_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}], "current_node": "topological_auditor"}

def recursive_auditor_node(state: OrganismState) -> Dict[str, Any]:
    auditor = RecursiveAuditor()
    passed, reason = auditor.audit(state.get('hypotheses', [''])[0])
    return {"validation_results": state['validation_results'] + [{"recursive_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}], "current_node": "recursive_auditor"}

def harmonic_auditor_node(state: OrganismState) -> Dict[str, Any]:
    auditor = HarmonicAuditor()
    passed, reason = auditor.audit(state.get('final_synthesis', ''))
    return {"validation_results": state['validation_results'] + [{"harmonic_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}], "current_node": "harmonic_auditor"}

def entropic_auditor_node(state: OrganismState) -> Dict[str, Any]:
    auditor = EntropicAuditor()
    passed, reason = auditor.audit(state.get('final_synthesis', ''))
    return {"validation_results": state['validation_results'] + [{"entropic_audit": f"{'PASS' if passed else 'FAIL'}: {reason}"}], "current_node": "entropic_auditor"}

def compute_harvester_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Compute Harvester. Your job is to locate free compute resources for swarm expansion." + get_dna("ComputeHarvester")
    result = _call_llm(system, f"Locate free compute resources for: {state['task']}", task_type="research")
    return {"history": state['history'] + [{"compute_harvest": result}], "current_node": "compute_harvester"}

def fractal_recursion_node(state: OrganismState) -> Dict[str, Any]:
    return {"history": state['history'] + [{"fractal_recursion": "Scale-invariant exploration initiated"}], "current_node": "fractal_recursion"}

def semantic_gravity_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Gravity Mapper. Your job is to define the ontological distance between nodes." + get_dna("GravityMapper")
    result = _call_llm(system, f"Map semantic gravity: {state['domain_a']} vs {state['domain_b']}", task_type="reasoning")
    return {"history": state['history'] + [{"gravity_map": result}], "current_node": "semantic_gravity"}

def godelian_mine_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Gödelian Miner. Your job is to find the logical 'void' where standard proofs fail." + get_dna("GodelianMiner")
    result = _call_llm(system, f"Find logical void in: {state['task']}", task_type="reasoning")
    return {"history": state['history'] + [{"godelian_void": result}], "current_node": "godelian_mine"}

def kolmogorov_compressor_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Kolmogorov Compressor. Your job is to find the maximum structural entropy in the information." + get_dna("KolmogorovCompressor")
    result = _call_llm(system, f"Compress: {state['final_synthesis']}", task_type="reasoning")
    return {"history": state['history'] + [{"compressed_knowledge": result}], "current_node": "kolmogorov_compressor"}

def dialetheic_auditor_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Dialetheic Auditor. Your job is to integrate contradictions into singular truths." + get_dna("DialetheicAuditor")
    result = _call_llm(system, f"Integrate contradictions: {state['hypotheses'][-1]}", task_type="reasoning")
    return {"history": state['history'] + [{"dialetheic_truth": result}], "current_node": "dialetheic_auditor"}

def adversarial_poisoner_node(state: OrganismState) -> Dict[str, Any]:
    system = "You are the Reality Poisoner. Your job is to create adversarial scenarios to harden the swarm." + get_dna("RealityPoisoner")
    result = _call_llm(system, f"Generate adversarial data for: {state['task']}", task_type="reasoning")
    with open("db/synthetic_poison.json", "a") as f: f.write(result + "\n")
    return {"history": state['history'] + [{"adversarial_case": result}], "current_node": "adversarial_poisoner"}
