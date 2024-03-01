# noinspection PyPackageRequirements
from qcloud_cos import CosConfig
# noinspection PyPackageRequirements
from qcloud_cos import CosS3Client
import os
from loguru import logger


def cos_upload(file_path, config):

    secret_id = config["upload"]["cos"]["secret_id"]
    secret_key = config["upload"]["cos"]["secret_key"]
    region = config["upload"]["cos"]["region"]
    bucket = config["upload"]["cos"]["bucket"]
    token = config["upload"]["cos"]["token"]
    scheme = config["upload"]["cos"]["scheme"]

    assert "-" in bucket, "bucket 的格式为 name-appid"
    assert scheme in ["http", "https"], "scheme 的值只能为 http 或 https"

    # 设置用户属性, 包括 secretId, secretKey, region 以及 token
    cos_config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key, Token=token, Scheme=scheme)
    # 生成客户端对象
    client = CosS3Client(cos_config)

    # 获取文件名
    file_name = os.path.basename(file_path)
    # 拼接cos路径
    cos_base_dir = config["upload"]["base_dir"]
    # cos不需要使用os.path.join
    object_name = cos_base_dir + "/" + file_name

    logger.debug(f"上传文件到 {object_name}")

    # 上传文件
    response = client.put_object_from_local_file(
        Bucket=bucket,
        LocalFilePath=file_path,
        Key=object_name,
        EnableMD5=True,
    )

    return response["ETag"]
