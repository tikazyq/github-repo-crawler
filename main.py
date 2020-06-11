import subprocess
from datetime import datetime
import os
import shutil

import git
from pymongo import MongoClient

from utils import is_repo_ready

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
col_github_repos = db.get_collection('results_github-crawler')


def set_config():
    subprocess.check_output(['git', 'config', '--global', 'https.proxy', 'http://149.129.63.159:80'])
    subprocess.check_output(['git', 'config', '--global', 'http.proxy', 'http://149.129.63.159:80'])


def clone_repo(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    url = f'https://github.com/{github_repo["full_name"]}'
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    stdout = subprocess.check_output(['git', 'clone', url, repo_path])
    print(stdout.decode('utf-8'))


def download_repo(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    repo_user_path = f'/data/github.com/{github_repo["full_name"].split("/")[0]}'
    if not os.path.exists(repo_user_path):
        os.mkdir(repo_user_path)

    subprocess.check_output([
        'curl',
        '-x', '149.129.63.159:80',
        f'https://codeload.github.com/{github_repo["full_name"]}/zip/master',
        '-o', '/tmp/master.zip'
    ])
    subprocess.check_output(['unzip', '/tmp/master.zip'])
    subprocess.check_output(['mv', f'{github_repo["name"]}-master', repo_path])
    subprocess.check_output(['rm', '/tmp/master.zip'])


def run():
    for repo in col_repos.find({'enabled': True}):
        print(repo)
        github_repo = col_github_repos.find_one({'_id': repo['github_repo_id']})
        if github_repo is None:
            continue
        print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] processing ' + github_repo['full_name'])
        if is_repo_ready(github_repo):
            continue
        try:
            download_repo(github_repo)
        except Exception as ex:
            print(ex)
            continue
        # clone_repo(github_repo)


if __name__ == '__main__':
    set_config()
    run()
