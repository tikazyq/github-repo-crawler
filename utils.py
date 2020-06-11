import os


def is_repo_ready(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    if not os.path.exists(repo_path):
        return False
    items = os.listdir(repo_path)
    if len(items) <= 1:
        return False
    return True
