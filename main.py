import subprocess
from datetime import datetime
import os
import shutil

import requests
from pymongo import MongoClient

import qiniu_utils
from utils import is_repo_ready, is_repo_has_readme

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

qiniu_bucket_name = 'crawlab-repo'


def clone_repo(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    url = f'https://github.com/{github_repo["full_name"]}'
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path)
    stdout = subprocess.check_output(['git', 'clone', url, repo_path])
    print(stdout.decode('utf-8'))


def download_repo(github_repo):
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] downloading ' + github_repo['full_name'])
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    repo_user_path = f'/data/github.com/{github_repo["full_name"].split("/")[0]}'
    if not os.path.exists(repo_user_path):
        os.mkdir(repo_user_path)

    subprocess.run([
        'curl',
        '-x', '149.129.63.159:80',
        f'https://codeload.github.com/{github_repo["full_name"]}/zip/master',
        '-o', '/tmp/master.zip',
    ], check=True)
    subprocess.run(['unzip', '/tmp/master.zip'], check=True)
    subprocess.run(['mv', f'{github_repo["name"]}-master', repo_path], check=True)
    subprocess.run(['rm', '/tmp/master.zip'], check=True)
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] downloaded ' + github_repo['full_name'])


def fetch_readme_text(github_repo):
    proxies = {
        "http": "http://149.129.63.159:80",
        "https": "http://149.129.63.159:80",
    }
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] fetching readme of ' + github_repo['full_name'])
    url = f'https://raw.githubusercontent.com/{github_repo["full_name"]}/master/README.md'
    r = requests.get(url, proxies=proxies)
    if r.status_code != 200:
        return
    content = r.content.decode('utf-8')
    col_repos.update_one({'github_repo_id': github_repo['_id']}, {'$set': {'readme_text': content}})
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] fetched readme of ' + github_repo['full_name'])


def upload_zip_files(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    zip_filedir = f'/tmp/{github_repo["full_name"].split("/")[0]}'
    if not os.path.exists(zip_filedir):
        os.mkdir(zip_filedir)
    zip_filepath = f'/tmp/{github_repo["full_name"]}.zip'
    qiniu_filepath = f'{github_repo["full_name"]}.zip'
    subprocess.run(['zip', '-r', zip_filepath, repo_path], check=True)
    qiniu_utils.upload(qiniu_bucket_name, zip_filedir, qiniu_filepath)


def run():
    for repo in col_repos.find({'enabled': True}):
        github_repo = col_github_repos.find_one({'_id': repo['github_repo_id']})
        if github_repo is None:
            continue
        print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] processing ' + github_repo['full_name'])
        if not is_repo_has_readme(repo):
            try:
                fetch_readme_text(github_repo)
            except Exception as ex:
                print(ex)

        if not is_repo_ready(github_repo):
            try:
                download_repo(github_repo)
            except Exception as ex:
                print(ex)

        repo_path = f'{github_repo["full_name"]}.zip'
        if not qiniu_utils.is_file_exist(qiniu_bucket_name, repo_path):
            upload_zip_files(github_repo)


if __name__ == '__main__':
    run()
