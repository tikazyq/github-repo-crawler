# -*- coding: utf-8 -*-
import json

from qiniu import Auth, put_file, etag, BucketManager

# 需要填写你的 Access Key 和 Secret Key
from qiniu.http import ResponseInfo

with open('credentials.json') as f:
    s = f.read()
    data = json.loads(s)
    access_key = data['qiniu']['access_key']
    secret_key = data['qiniu']['secret_key']

# 构建鉴权对象
q = Auth(access_key, secret_key)

# 初始化BucketManager
bucket = BucketManager(q)


# 要上传文件的本地路径
def upload(bucket_name: str, local_path: str, target_name: str):
    # 上传后保存的文件名
    key = target_name

    # 生成上传 Token，可以指定过期时间等
    token = q.upload_token(bucket_name, key, 3600)

    # 上传文件
    ret, info = put_file(token, key, local_path)
    print(info)
    assert ret['key'] == key
    assert ret['hash'] == etag(local_path)


def get_file_info(bucket_name: str, target_name: str) -> ResponseInfo:
    ret, info = bucket.stat(bucket_name, target_name)
    return ret, info


def is_file_exist(bucket_name: str, target_name: str) -> bool:
    ret, info = bucket.stat(bucket_name, target_name)

    if ret is None:
        return False
    return 'hash' in ret


if __name__ == '__main__':
    bucket_name = 'crawlab-repo'
    print(is_file_exist(bucket_name, 'favicon.ico'))
    print(is_file_exist(bucket_name, 'favicon1.ico'))
