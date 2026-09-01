import boto3
from botocore.exceptions import ClientError

from app.storage.base import ObjectNotFound


class R2Storage:
    """Cloudflare R2 is S3 compatible, so this is boto3 pointed at R2's endpoint.

    Written but NOT verified against a live bucket, because this exercise has
    no bucket to verify against. The README says so rather than implying it
    has been exercised in anger.
    """

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint_url: str,
        public_base_url: str,
    ):
        self.bucket = bucket
        self.public_base_url = public_base_url.rstrip("/")
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
        )

    def put(self, key: str, data: bytes, content_type: str) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return self.url(key)

    def get(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            raise ObjectNotFound(key) from exc

    def url(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
