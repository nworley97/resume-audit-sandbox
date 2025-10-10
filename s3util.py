"""
s3util.py  –  helper for S3 uploads + presigned downloads, with persistent-disk fallback.

Behavior by environment:
- If AWS creds/bucket are set (AWS_S3_BUCKET), use S3:
    upload_pdf(path) -> "s3://<bucket>/resumes/<uuid>.<ext>"
    presign(s3_url)  -> HTTPS presigned GET URL
    delete_s3(s3_url)-> delete object from S3
- Else if PERSIST_DIR is set (e.g., /var/data mounted via Render Persistent Disk):
    upload_pdf(path) -> "<PERSIST_DIR>/<uuid>.<ext>" (copied there; persists across deploys)
- Else (no S3, no disk):
    upload_pdf(path) -> original local path (ephemeral; NOT persistent)

Environment variables
---------------------
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_S3_BUCKET          # bucket name (e.g. blackbox-resumes-prod)
AWS_S3_REGION          # region (e.g. us-east-1) – optional; boto3 can infer

PERSIST_DIR            # e.g. /var/data (Render Persistent Disk mount path)
"""

import os, uuid, pathlib, shutil
import boto3

BUCKET = os.getenv("AWS_S3_BUCKET", "")
S3_ENABLED = bool(BUCKET)

# Persistent disk path (Render Persistent Disk). Example: /var/data
PERSIST_DIR = os.getenv("PERSIST_DIR", "")

if S3_ENABLED:
    s3 = boto3.client("s3", region_name=os.getenv("AWS_S3_REGION"))

def upload_pdf(path: str) -> str:
    """
    Uploads the given PDF/DOCX and returns a storage URL or persistent path.

    Returns:
      - S3 mode: "s3://<bucket>/resumes/<uuid>.<ext>"
      - Disk mode: "<PERSIST_DIR>/<uuid>.<ext>"
      - Ephemeral: original path
    """
    suffix = pathlib.Path(path).suffix

    # S3 mode
    if S3_ENABLED:
        key = f"resumes/{uuid.uuid4()}{suffix}"
        s3.upload_file(path, BUCKET, key)
        return f"s3://{BUCKET}/{key}"

    # Persistent disk mode
    if PERSIST_DIR:
        os.makedirs(PERSIST_DIR, exist_ok=True)
        dest = os.path.join(PERSIST_DIR, f"{uuid.uuid4()}{suffix}")
        shutil.copy2(path, dest)
        return dest

    # Ephemeral fallback (not persistent)
    return path

def presign(
    s3_url: str,
    expires: int = 3600,
    *,
    content_disposition: str | None = None,
    content_type: str | None = None,
) -> str:
    """
    Generates a presigned HTTPS GET link from an s3://bucket/key URL.
    Optional response headers can be overridden using:
      - content_disposition (e.g., 'inline' or 'attachment; filename="name.pdf"')
      - content_type (e.g., 'application/pdf')
    Only valid when S3 is enabled.
    """
    if not S3_ENABLED:
        raise RuntimeError("presign() called without S3 enabled")
    bucket, key = s3_url.split("/", 3)[2], s3_url.split("/", 3)[3]
    params = {"Bucket": bucket, "Key": key}
    if content_disposition:
        params["ResponseContentDisposition"] = content_disposition
    if content_type:
        params["ResponseContentType"] = content_type
    return s3.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires,
    )

def delete_s3(s3_url: str) -> None:
    """
    Deletes an object at s3://bucket/key. No-op if S3 disabled.
    """
    if not S3_ENABLED or not s3_url.startswith("s3://"):
        return
    bucket, key = s3_url.split("/", 3)[2], s3_url.split("/", 3)[3]
    s3.delete_object(Bucket=bucket, Key=key)
