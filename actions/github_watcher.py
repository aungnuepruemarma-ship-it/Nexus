from github import Github
import os

class GithubWatcher:
    def __init__(self, token):
        self.g = Github(token)

    def check_starred_repos(self, user):
        """Checks for new releases in starred repositories."""
        user = self.g.get_user(user)
        new_anomalies = []
        for repo in user.get_starred():
            # Simplistic check: if repo was updated in last hour
            if repo.updated_at > (os.path.getmtime("db/dna.json") - 3600):
                new_anomalies.append(f"Repo {repo.full_name} updated.")
        return new_anomalies
