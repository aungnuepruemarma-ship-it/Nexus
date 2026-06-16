from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

class TelemetryManager:
    def __init__(self, job_name="nexus_organism"):
        self.registry = CollectorRegistry()
        self.discovery_gauge = Gauge('discovery_throughput', 'Number of discoveries', registry=self.registry)
        self.latency_gauge = Gauge('agent_latency', 'Agent latency', ['agent'], registry=self.registry)
        self.job_name = job_name

    def record_discovery(self, count):
        self.discovery_gauge.set(count)

    def record_latency(self, agent, latency):
        self.latency_gauge.labels(agent=agent).set(latency)
