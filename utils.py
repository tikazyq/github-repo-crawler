# -*- coding: utf-8 -*-
import os
import sys
import zipfile


def is_repo_ready(github_repo):
    repo_path = f'/data/github.com/{github_repo["full_name"]}'
    if not os.path.exists(repo_path):
        return False
    items = os.listdir(repo_path)
    if len(items) <= 1:
        return False
    return True


def is_repo_has_readme(repo):
    return repo.get('readme_text') is not None


def get_zip_file(input_path, result):
    """
    对目录进行深度优先遍历
    :param input_path:
    :param result:
    :return:
    """
    files = os.listdir(input_path)
    for file in files:
        if os.path.isdir(os.path.join(input_path, file)):
            get_zip_file(os.path.join(input_path, file), result)
        else:
            result.append(os.path.join(input_path, file))


def zip_dir(input_path, output_filepath):
    """
    压缩文件
    """
    f = zipfile.ZipFile(output_filepath, 'w', zipfile.ZIP_DEFLATED)
    filelists = []
    get_zip_file(input_path, filelists)
    for file in filelists:
        f.write(file)
    # 调用了close方法才会保证完成压缩
    f.close()
