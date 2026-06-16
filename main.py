import argparse
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.orchestrator import NexusOrchestrator
from core.meta_orchestrator import MetaDiscoveryOrchestrator
from core.daemon import NexusDaemon
from motivation.need_matrix import NeedMatrix
from memory.hippocampus import Hippocampus
from evolution.self_evolution import SelfEvolution
from actions.arxiv_anchor import ArxivAnchor
from actions.economic_simulator import EconomicBacktester

load_dotenv()

def run_organism(task: str, domain_a: str, domain_b: str):
    print(f"🧠 INITIALIZING NEXUS ORGANISM...")

    # Initialize components
    orchestrator = NexusOrchestrator()
    needs = NeedMatrix()
    memory = Hippocampus()
    evolution = SelfEvolution()
    anchor = ArxivAnchor(memory)
    tester = EconomicBacktester()

    # Cybernetic Homeostasis Sync
    needs.sync_metabolism()

    # 1. Reality Anchor (arXiv Grounding)
    anchor.anchor_knowledge(domain_a)
    print(f"🚀 TASK: {task}")
    print(f"🧪 DOMAIN A: {domain_a}")
    print(f"🧪 DOMAIN B: {domain_b}")
    print("-" * 30)

    # 2. Run the tournament
    final_state = orchestrator.run(task, domain_a, domain_b)

    # 3. Capital Loop (Economic Backtest)
    if final_state['final_synthesis']:
        econ_results = tester.backtest_discovery(final_state['final_synthesis'])
        print(f"📈 ECONOMIC VIABILITY: {econ_results['total_gain_percent']:.2f}% gain predicted.")

    print("\n✅ TOURNAMENT COMPLETE")
    # ... rest of the synthesis logic

    print("FINAL SYNTHESIS:")
    print(final_state['final_synthesis'])
    print("-" * 30)
    
    # Store in memory
    memory.add_memory(
        content=final_state['final_synthesis'],
        metadata={"task": task, "domain_a": domain_a, "domain_b": domain_b}
    )
    
    # Update needs
    if final_state['final_synthesis']:
        needs.update_on_novelty()
    else:
        needs.update_on_error()
    needs.save()
    
    # Self-Evolution
    mutation = evolution.audit_run(final_state)
    evolution.apply_mutation(mutation)
    
    print(f"\n📊 STATE: curiosity={needs.curiosity_score:.2f}, energy={needs.compute_energy}")

async def run_meta_organism(task: str, pairs: list):
    print(f"🧠 INITIALIZING META-NEXUS ORGANISM...")
    meta = MetaDiscoveryOrchestrator()
    
    print(f"🚀 TASK: {task}")
    print(f"🧪 RUNNING {len(pairs)} PARALLEL TOURNAMENTS...")
    
    results = await meta.run_parallel_tournaments(task, pairs)
    synthesis = meta.meta_synthesize(results)
    
    print("\n✅ META-TOURNAMENT COMPLETE")
    print("-" * 30)
    print("META-SYNTHESIS:")
    print(synthesis)
    print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nexus Organism: Autonomous Discovery Engine")
    parser.add_argument("--task", type=str, default="Find the mathematical link between slime mold foraging and decentralized finance liquidity pools")
    parser.add_argument("--domain_a", type=str, default="Physarum polycephalum foraging network optimization")
    parser.add_argument("--domain_b", type=str, default="DeFi liquidity pool rebalancing algorithms")
    parser.add_argument("--demo", action="store_true", help="Run the default demo tournament")
    parser.add_argument("--meta", action="store_true", help="Run meta-discovery (parallel tournaments)")
    parser.add_argument("--daemon", action="store_true", help="Run the discovery daemon in the background")
    
    args = parser.parse_args()
    
    if args.daemon:
        NexusDaemon().start()
    if args.meta:
        pairs = [
            ("Metal-Organic Frameworks (MOFs) synthesis", "Stochastic Network Optimization"),
            ("Multi-Agent System (MAS) Consensus Protocols", "Biological Colony Quorum Sensing"),
            ("Biological Metabolic Pathway Regulation", "JIT Compiler Instruction Scheduling")
        ]
        asyncio.run(run_meta_organism(args.task, pairs))

    elif args.demo:
        run_organism(
            "Find the mathematical link between slime mold foraging and decentralized finance liquidity pools",
            "Physarum polycephalum foraging network optimization",
            "DeFi liquidity pool rebalancing algorithms"
        )
    else:
        run_organism(args.task, args.domain_a, args.domain_b)
