import subprocess
import os

class GitAgent:
    def __init__(self, repo_path):
        self.repo_path = repo_path

    def draft_pr(self, feature_name, file_content, file_path):
        branch_name = f"discovery/{feature_name}"
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], cwd=self.repo_path, check=True)
            with open(os.path.join(self.repo_path, file_path), "w") as f:
                f.write(file_content)
            subprocess.run(["git", "add", file_path], cwd=self.repo_path, check=True)
            subprocess.run(["git", "commit", "-m", f"Auto-draft: {feature_name}"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "push", "origin", branch_name], cwd=self.repo_path, check=True)
            return f"PR Drafted: {branch_name}"
        except Exception as e:
            return f"Git PR Draft failed: {e}"

    def auto_merge(self, branch_name):
        """Merges a discovery branch after validation (USE WITH EXTREME CAUTION)."""
        try:
            subprocess.run(["git", "checkout", "main"], cwd=self.repo_path, check=True)
            subprocess.run(["git", "merge", branch_name], cwd=self.repo_path, check=True)
            subprocess.run(["git", "push", "origin", "main"], cwd=self.repo_path, check=True)
            return f"Auto-merged: {branch_name} into main"
        except Exception as e:
            return f"Git Auto-merge failed: {e}"
