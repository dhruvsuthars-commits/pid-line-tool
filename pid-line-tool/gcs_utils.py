"""Simple GCS helpers for upload/download and signed URLs."""
from google.cloud import storage
import os
from datetime import timedelta


def _get_client():
    return storage.Client()


def upload_file(bucket_name: str, dest_path: str, local_path: str):
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_path)
    blob.upload_from_filename(local_path)
    return blob.name


def download_file(bucket_name: str, src_path: str, local_path: str):
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(src_path)
    os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
    blob.download_to_filename(local_path)
    return local_path


def generate_signed_url(bucket_name: str, blob_name: str, expires_seconds: int = 3600):
    client = _get_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    url = blob.generate_signed_url(expiration=timedelta(seconds=expires_seconds))
    return url
