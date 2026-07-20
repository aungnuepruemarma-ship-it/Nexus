"""The Dream layer: the Automated Computer Scientist that drives CCS autonomously.

A small local open-source model proposes/narrates hypotheses, a web-browsing ability fetches
outside context, and the DreamEngine loops — hypothesis -> real experiment -> falsification ->
registry update -> git commit — turning the scientific method itself into software.
"""
from .model import LocalModel
from .web import WebBrowser
from .sandbox import Sandbox
from .actions import GuardedActions
from .engine import DreamEngine, Dream
from .generator import ExperimentGenerator
from .memory_graph import MemoryGraph
from .planner import ResearchPlanner
from .reviewer import ReviewPanel
from . import causal

__all__ = [
    "LocalModel", "WebBrowser", "DreamEngine", "Dream", "Sandbox", "GuardedActions",
    "ExperimentGenerator", "MemoryGraph", "ResearchPlanner", "ReviewPanel", "causal",
]
