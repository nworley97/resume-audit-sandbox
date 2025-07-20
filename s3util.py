import boto3, os, uuid, botocore

s3 = boto3.client(
    "s3",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_S3_REGION")
)
bucket = os.getenv("AWS_S3_BUCKET")

def upload_pdf(path) -> str:
    key = f"resumes/{uuid.uuid4()}.pdf"
    s3.upload_file(path, bucket, key,
                   ExtraArgs={"ContentType": "application/pdf", "ACL": "private"})
    return f"s3://{bucket}/{key}"

def presign(s3_url, expires=3600):
    _, b, k = s3_url.split("/", 2)
    return s3.generate_presigned_url(
        "get_object", Params={"Bucket": b, "Key": k}, ExpiresIn=expires
    )

def get_job_description() -> str:
    try:
        obj = s3.get_object(Bucket=bucket, Key="config/jd.html")
        return obj["Body"].read().decode("utf-8")
    except botocore.exceptions.ClientError:
        return "<h4>No job description yet</h4>"