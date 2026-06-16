import unittest
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.hippocampus import Hippocampus
from motivation.need_matrix import NeedMatrix
from sandbox.prover import Prover

class TestNexusComponents(unittest.TestCase):
    def test_hippocampus(self):
        db_path = "db/test_memory.json"
        if os.path.exists(db_path):
            os.remove(db_path)
        
        hp = Hippocampus(db_path=db_path)
        hp.add_memory("The quick brown fox", metadata={"tag": "animal"})
        memories = hp.query_memories("fox")
        
        self.assertTrue(len(memories) > 0)
        self.assertIn("fox", memories[0].lower())
        
        if os.path.exists(db_path):
            os.remove(db_path)

    def test_need_matrix(self):
        state_file = "db/test_needs.json"
        if os.path.exists(state_file):
            os.remove(state_file)
            
        nm = NeedMatrix(state_file=state_file)
        initial_curiosity = nm.curiosity_score
        nm.update_on_novelty(0.1)
        
        self.assertEqual(nm.curiosity_score, min(1.0, initial_curiosity + 0.1))
        self.assertEqual(nm.compute_energy, 9)
        
        if os.path.exists(state_file):
            os.remove(state_file)

    def test_prover(self):
        pv = Prover()
        code = "print('Hello Nexus')"
        result = pv.execute_code(code)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['stdout'].strip(), "Hello Nexus")

if __name__ == "__main__":
    unittest.main()
