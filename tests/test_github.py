from actions.github_watcher import GithubWatcher
import os
import sys

if len(sys.argv) < 2:
    print("Usage: python test_github.py <your_github_username>")
    sys.exit(1)

username = sys.argv[1]
token = os.getenv("GITHUB_TOKEN")

if not token:
    print("Error: GITHUB_TOKEN environment variable not set.")
    sys.exit(1)

print(f"Testing GitHub connection for user: {username}...")
watcher = GithubWatcher(token=token)
try:
    repos = watcher.check_starred_repos(user=username)
    print(f"Successfully connected to GitHub. Found {len(repos)} recent updates/anomalies.")
    for repo in repos:
        print(f"- {repo}")
except Exception as e:
    print(f"GitHub test failed: {e}")
