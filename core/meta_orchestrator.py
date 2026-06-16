import asyncio
from core.orchestrator import NexusOrchestrator

class MetaDiscoveryOrchestrator:
    def __init__(self):
        self.orchestrator = NexusOrchestrator()

    async def run_parallel_tournaments(self, task: str, domain_pairs: list):
        results = []
        for pair in domain_pairs:
            # Run sequentially to avoid rate limits
            results.append(self.orchestrator.run(task, pair[0], pair[1]))
        return results

    def meta_synthesize(self, results):
        # A simple synthesis of all tournament results
        syntheses = [r['final_synthesis'] for r in results if r['final_synthesis']]
        return "\n\n---\n\n".join(syntheses)
