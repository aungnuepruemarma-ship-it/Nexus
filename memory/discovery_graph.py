import networkx as nx
import json
import os

class DiscoveryGraph:
    def __init__(self, graph_file="db/discovery_graph.gexf"):
        self.graph_file = graph_file
        if os.path.exists(graph_file):
            self.graph = nx.read_gexf(graph_file)
        else:
            self.graph = nx.DiGraph()

    def add_discovery(self, domain_a, domain_b, discovery_summary):
        if not self.graph.has_node(domain_a):
            self.graph.add_node(domain_a, type="domain")
        if not self.graph.has_node(domain_b):
            self.graph.add_node(domain_b, type="domain")
        
        self.graph.add_edge(domain_a, domain_b, weight=1, summary=discovery_summary)
        self.save()

    def save(self):
        nx.write_gexf(self.graph, self.graph_file)

    def get_neighbors(self, domain):
        return list(self.graph.neighbors(domain))
