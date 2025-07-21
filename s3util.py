"""
s3util.py  –  tiny helper for S3 uploads + presigned downloads.

* If AWS creds / bucket are NOT set, the module falls back to “local mode”:
  - upload_pdf(path) simply returns the original local path
  - download code in app.py will send the file with send_file()

Environment variables expected for S3 mode
------------------------------------------
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_S3_BUCKET            # bucket name (e.g. my‑resume‑bucket)
AWS_S3_REGION            # region (e.g. us‑east‑1)  – optional; boto3 infers
"""

import os, uuid, pathlib
import boto3

BUCKET = os.getenv("AWS_S3_BUCKET", "")
S3_ENABLED = bool(BUCKET)

if S3_ENABLED:
    # create once, reuse
    s3 = boto3.client("s3", region_name=os.getenv("AWS_S3_REGION"))

def upload_pdf(path: str) -> str:
    """
    Uploads the given PDF (or DOCX) and returns a storage URL.

    * S3 enabled  ->  's3://bucket/key'
    * Local mode  ->  original path (caller will send_file)
    """
    if not S3_ENABLED:
        return path

    key = f"resumes/{uuid.uuid4()}{pathlib.Path(path).suffix}"
    s3.upload_file(path, BUCKET, key)
    return f"s3://{BUCKET}/{key}"

def presign(s3_url: str, expires: int = 3600) -> str:
    """
    Generates a presigned HTTPS GET link from an s3://bucket/key URL.
    """
    bucket, key = s3_url.split("/", 3)[2], s3_url.split("/", 3)[3]
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
