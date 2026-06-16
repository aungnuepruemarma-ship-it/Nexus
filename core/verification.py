import os
import json
import subprocess
from sandbox.prover import Prover

class VerificationEngine:
    def __init__(self, codebase_path):
        self.codebase_path = codebase_path

    def verify_refactor(self, file_path, new_code):
        """Runs the test suite against proposed refactor."""
        # Save proposed code to a temp file
        with open("proposed_refactor.py", "w") as f:
            f.write(new_code)
        
        # Run test suite
        prover = Prover()
        result = prover.execute_code("import unittest; from tests import test_core; suite = unittest.TestLoader().loadTestsFromModule(test_core); runner = unittest.TextTestRunner(); runner.run(suite)")
        
        if result['success']:
            os.rename("proposed_refactor.py", file_path)
            return True
        else:
            return False
