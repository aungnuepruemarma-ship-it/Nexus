import streamlit as st
import json
import os
import pandas as pd
from actions.git_agent import GitAgent

st.set_page_config(page_title="Nexus Organism Dashboard", layout="wide")

st.title("🧠 Nexus Organism Dashboard")

# User Guidance (Steering)
st.sidebar.header("Human Steering")
pinned_domain = st.sidebar.text_input("Pin a Domain to Explore")
if st.sidebar.button("Pin Domain"):
    with open("db/user_guidance.json", "w") as f:
        json.dump({"pinned_domain": pinned_domain}, f)
    st.sidebar.success(f"Pinned: {pinned_domain}")

# Load DNA
dna_file = "db/dna.json"
if os.path.exists(dna_file):
    with open(dna_file, 'r') as f:
        dna = json.load(f)
else:
    dna = {}

st.sidebar.header("Evolutionary DNA")
for agent, instructions in dna.items():
    with st.sidebar.expander(agent):
        for instr in instructions:
            st.write(f"- {instr}")

# Load Memories
mem_file = "db/memory.json"
if os.path.exists(mem_file):
    with open(mem_file, 'r') as f:
        memories = json.load(f)
else:
    memories = []

st.header("Discovery Logs")
for i, mem in enumerate(memories):
    with st.expander(f"Task: {mem.get('metadata', {}).get('task', 'Unknown')}"):
        st.write(mem.get('content'))
        if st.button(f"Draft PR for discovery {i}", key=f"pr_{i}"):
            git = GitAgent(repo_path=".")
            result = git.draft_pr(f"discovery-{i}", mem.get('content'), f"discovery_report_{i}.md")
            st.write(result)

if st.button("Refresh"):
    st.rerun()
