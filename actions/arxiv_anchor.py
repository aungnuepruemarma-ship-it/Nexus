import arxiv
from memory.hippocampus import Hippocampus

class ArxivAnchor:
    def __init__(self, hippocampus: Hippocampus):
        self.hp = hippocampus

    def anchor_knowledge(self, topic, max_results=3):
        """Fetches real papers to ground the swarm's knowledge."""
        print(f"⚓ ARXIV ANCHOR: Grounding knowledge on {topic}...")
        client = arxiv.Client()
        search = arxiv.Search(
            query=topic,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        for result in client.results(search):
            summary = f"PAPER: {result.title}\nSUMMARY: {result.summary}"
            self.hp.add_memory(summary, metadata={"source": "arxiv", "topic": topic})
            print(f"⚓ ARXIV ANCHOR: Ingested {result.title}")
