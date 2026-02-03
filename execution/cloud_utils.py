import os
from google.cloud import storage
import glob
from datetime import datetime

def get_gcs_client():
    return storage.Client()

def upload_to_gcs(local_path, bucket_name, destination_blob_name):
    """Uploads a file to the bucket."""
    try:
        storage_client = get_gcs_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)

        blob.upload_from_filename(local_path)

        print(f"[CLOUD] File {local_path} uploaded to gs://{bucket_name}/{destination_blob_name}")
        return True
    except Exception as e:
        print(f"[CLOUD ERROR] Upload Failed: {e}")
        return False

def download_from_gcs(bucket_name, source_blob_name, destination_file_name):
    """Downloads a blob from the bucket."""
    try:
        storage_client = get_gcs_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(source_blob_name)

        blob.download_to_filename(destination_file_name)

        print(f"[CLOUD] Blob {source_blob_name} downloaded to {destination_file_name}.")
        return destination_file_name
    except Exception as e:
        print(f"[CLOUD ERROR] Download Failed: {e}")
        return None

def get_latest_file_from_gcs(bucket_name, prefix="raw_data/"):
    """Finds the latest file in the bucket folder."""
    try:
        storage_client = get_gcs_client()
        blobs = storage_client.list_blobs(bucket_name, prefix=prefix)
        
        all_blobs = list(blobs)
        if not all_blobs:
            return None

        # Sort by updated time (newest first)
        latest_blob = max(all_blobs, key=lambda b: b.updated)
        print(f"[CLOUD] Found latest blob: {latest_blob.name}")
        return latest_blob.name
    except Exception as e:
        print(f"[CLOUD ERROR] List Failed: {e}")
    except Exception as e:
        print(f"[CLOUD ERROR] List Failed: {e}")
        return None

def sync_config_to_gcs(bucket_name, local_config_path="config.json"):
    """Backs up local config to Cloud Storage."""
    return upload_to_gcs(local_config_path, bucket_name, "config/config.json")

def sync_config_from_gcs(bucket_name, local_config_path="config.json"):
    """Restores config from Cloud Storage."""
    return download_from_gcs(bucket_name, "config/config.json", local_config_path)
