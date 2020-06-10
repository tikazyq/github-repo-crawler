from datetime import datetime
import os
import shutil

import git
from pymongo import MongoClient

MONGO_HOST = os.environ.get('CRAWLAB_MONGO_HOST') or 'localhost'
MONGO_PORT = int(os.environ.get('CRAWLAB_MONGO_PORT') or 27017) or 27017
MONGO_DB = os.environ.get('CRAWLAB_MONGO_DB') or 'test'
MONGO_USERNAME = os.environ.get('CRAWLAB_MONGO_USERNAME') or ''
MONGO_PASSWORD = os.environ.get('CRAWLAB_MONGO_PASSWORD') or ''
MONGO_AUTHSOURCE = os.environ.get('CRAWLAB_MONGO_AUTHSOURCE') or 'admin'
COLLECTION = os.environ.get('CRAWLAB_COLLECTION') or 'test'
mongo = MongoClient(
    host=MONGO_HOST,
    port=MONGO_PORT,
    username=MONGO_USERNAME,
    password=MONGO_PASSWORD,
    authSource=MONGO_AUTHSOURCE,
)
db = mongo.get_database(MONGO_DB)
col_repos = db.get_collection('cc_repos')
col_github_repos = db.get_collection(COLLECTION)


def clone_repo(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    url = f'https://github.com/{github_repo["full_name"]}'
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    git.Repo.clone_from(url, repo_path, branch='master')


def run():
    for repo in col_repos.find({'enabled': True}):
        github_repo = col_github_repos.find_one({'_id': repo['github_repo_id']})
        print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] processing ' + github_repo['full_name'])
        clone_repo(github_repo)
        break
