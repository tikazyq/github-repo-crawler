import subprocess
from datetime import datetime
import os
import shutil

import requests
from pymongo import MongoClient
from elasticsearch import Elasticsearch

import qiniu_utils
from utils import is_repo_ready, is_repo_has_readme, zip_dir

# mongo 配置
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

# 七牛配置
qiniu_bucket_name = 'crawlab-repo'

# ES 配置
ES_HOST = os.environ.get('ES_HOST')
ES_PORT = os.environ.get('ES_PORT')
ES_INDEX = os.environ.get('ES_INDEX')
es = Elasticsearch(hosts=[f'{ES_HOST}:{ES_PORT}'])


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

    proxies = {
        "http": "http://149.129.63.159:14128",
        "https": "http://149.129.63.159:14128",
    }
    url = f'https://codeload.github.com/{github_repo["full_name"]}/zip/master'
    # res = requests.get(url, proxies=proxies)
    res = requests.get(url)
    with open('/tmp/master.zip', 'wb') as f:
        f.write(res.content)
    subprocess.run(['unzip', '/tmp/master.zip'], check=True)
    subprocess.run(['mv', f'{github_repo["name"]}-master', repo_path], check=True)
    subprocess.run(['rm', '/tmp/master.zip'], check=True)
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] downloaded ' + github_repo['full_name'])


def fetch_readme_text(github_repo):
    proxies = {
        "http": "http://149.129.63.159:14128",
        "https": "http://149.129.63.159:14128",
    }
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] fetching readme of ' + github_repo['full_name'])
    url = f'https://raw.githubusercontent.com/{github_repo["full_name"]}/master/README.md'
    # r = requests.get(url, proxies=proxies)
    r = requests.get(url)
    if r.status_code != 200:
        return
    content = r.content.decode('utf-8')
    col_repos.update_one({'github_repo_id': github_repo['_id']}, {'$set': {'readme_text': content}})
    print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] fetched readme of ' + github_repo['full_name'])


def upload_zip_files(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    zip_file_dir = f'/tmp/{github_repo["full_name"].split("/")[0]}'
    if not os.path.exists(zip_file_dir):
        os.makedirs(zip_file_dir)
    zip_filepath = f'/tmp/{github_repo["full_name"]}.zip'
    qiniu_filepath = f'{github_repo["full_name"]}.zip'
    zip_dir(repo_path, zip_filepath)
    qiniu_utils.upload(qiniu_bucket_name, zip_filepath, qiniu_filepath)


def upload_sub_dir_zip_files(github_repo, sub_dir):
    repo_path = f'/data/github.com/{github_repo["full_name"]}/{sub_dir}'
    zip_file_dir = f'/tmp/{github_repo["full_name"]}'
    if not os.path.exists(zip_file_dir):
        os.makedirs(zip_file_dir)
    zip_filepath = f'/tmp/{github_repo["full_name"]}/{sub_dir}.zip'
    qiniu_filepath = f'{github_repo["full_name"]}/{sub_dir}.zip'
    zip_dir(repo_path, zip_filepath)
    qiniu_utils.upload(qiniu_bucket_name, zip_filepath, qiniu_filepath)


def index_es_repo(repo, github_repo):
    github_repo['id'] = str(repo['_id'])
    github_repo['is_sub_dir'] = repo.get('is_sub_dir') or False
    github_repo['readme_text'] = repo.get('readme_text')
    del github_repo['_id']
    es.index(
        index=ES_INDEX,
        body=github_repo,
        id=github_repo['id'],
    )


def run():
    for repo in col_repos.find({'enabled': True}):
        github_repo = col_github_repos.find_one({'_id': repo['github_repo_id']})
        if github_repo is None:
            continue
        print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] processing ' + github_repo['full_name'])

        # 下载 README
        if not is_repo_has_readme(repo):
            try:
                print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] fetching readme ' + github_repo['full_name'])
                fetch_readme_text(github_repo)
            except Exception as ex:
                print(ex)
        github_repo = col_github_repos.find_one({'_id': repo['github_repo_id']})

        # 下载 Repo
        if not is_repo_ready(github_repo):
            try:
                print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] downloading repo ' + github_repo['full_name'])
                download_repo(github_repo)
            except Exception as ex:
                print(ex)

        # 上传 Repo 到 OSS
        qiniu_repo_path = f'{github_repo["full_name"]}.zip'
        if not qiniu_utils.is_file_exist(qiniu_bucket_name, qiniu_repo_path):
            try:
                print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] upload zip files ' + github_repo['full_name'])
                upload_zip_files(github_repo)
            except Exception as ex:
                print(ex)

        # 上传 Repo 子目录到 OSS
        if repo.get('is_sub_dir'):
            print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] upload sub-dir zip files ' + github_repo['full_name'])
            repo_path = f'/data/github.com/{github_repo["full_name"]}'
            for sub_dir in os.listdir(repo_path):
                qiniu_repo_path = f'{github_repo["full_name"]}/{sub_dir}.zip'
                if os.path.isdir(f'{repo_path}/{sub_dir}') and not sub_dir.startswith('.') and not qiniu_utils.is_file_exist(qiniu_bucket_name, qiniu_repo_path):
                    try:
                        print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] upload ' + github_repo['full_name'] + '/' + sub_dir)
                        upload_sub_dir_zip_files(github_repo, sub_dir)
                    except Exception as ex:
                        print(ex)

        # 加入 ES 索引
        try:
            print('[' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '] index es repo ' + github_repo['full_name'])
            index_es_repo(repo, github_repo)
        except Exception as ex:
            print(ex)


if __name__ == '__main__':
    run()
