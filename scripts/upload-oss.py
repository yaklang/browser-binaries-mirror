#!/usr/bin/env python3
"""Publish immutable releases and mutable manifest objects to Aliyun OSS."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

import oss2

from mirrorlib import PRODUCT_PREFIX, load_json, sha256_file

IMMUTABLE_CACHE = "public, max-age=31536000, immutable"
MANIFEST_CACHE = "public, max-age=300, must-revalidate"


def normalized_headers(result: object) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in getattr(result, "headers", {}).items()}


def put_immutable(
    bucket: oss2.Bucket,
    key: str,
    local_path: Path,
    content_type: str,
    expected_payload_sha256: str,
) -> None:
    expected_file_sha256 = sha256_file(local_path)
    if expected_payload_sha256 != expected_file_sha256:
        raise ValueError(f"local SHA-256 mismatch before upload: {local_path}")
    try:
        existing = bucket.head_object(key)
    except oss2.exceptions.NoSuchKey:
        existing = None
    if existing is not None:
        headers = normalized_headers(existing)
        if (
            int(existing.content_length) == local_path.stat().st_size
            and headers.get("x-oss-meta-sha256") == expected_file_sha256
        ):
            print(f"immutable object already matches, skipping: oss://{bucket.bucket_name}/{key}")
            return
        raise RuntimeError(f"refusing to overwrite non-matching immutable object: {key}")

    headers = {
        "Content-Type": content_type,
        "Cache-Control": IMMUTABLE_CACHE,
        "x-oss-meta-sha256": expected_file_sha256,
        "x-oss-forbid-overwrite": "true",
    }
    if local_path.stat().st_size >= 100 * 1024 * 1024:
        oss2.resumable_upload(
            bucket,
            key,
            str(local_path),
            multipart_threshold=100 * 1024 * 1024,
            part_size=16 * 1024 * 1024,
            num_threads=4,
            headers=headers,
        )
    else:
        bucket.put_object_from_file(key, str(local_path), headers=headers)
    published = bucket.head_object(key)
    published_headers = normalized_headers(published)
    if int(published.content_length) != local_path.stat().st_size:
        raise RuntimeError(f"OSS Content-Length mismatch after upload: {key}")
    if published_headers.get("x-oss-meta-sha256") != expected_file_sha256:
        raise RuntimeError(f"OSS SHA-256 metadata mismatch after upload: {key}")


def put_mutable(bucket: oss2.Bucket, key: str, local_path: Path, content_type: str) -> None:
    digest = sha256_file(local_path)
    try:
        existing = bucket.head_object(key)
    except oss2.exceptions.NoSuchKey:
        existing = None
    if existing is not None:
        headers = normalized_headers(existing)
        if int(existing.content_length) == local_path.stat().st_size and headers.get("x-oss-meta-sha256") == digest:
            print(f"mutable object already matches, skipping: oss://{bucket.bucket_name}/{key}")
            return
    bucket.put_object_from_file(
        key,
        str(local_path),
        headers={
            "Content-Type": content_type,
            "Cache-Control": MANIFEST_CACHE,
            "x-oss-meta-sha256": digest,
        },
    )
    published = bucket.head_object(key)
    headers = normalized_headers(published)
    if int(published.content_length) != local_path.stat().st_size or headers.get("x-oss-meta-sha256") != digest:
        raise RuntimeError(f"mutable object verification failed after upload: {key}")


def make_bucket(args: argparse.Namespace) -> oss2.Bucket:
    key_id = os.environ.get("OSS_KEY_ID", "")
    key_secret = os.environ.get("OSS_KEY_SECRET", "")
    if not key_id or not key_secret:
        raise RuntimeError("OSS_KEY_ID and OSS_KEY_SECRET must be configured")
    return oss2.Bucket(oss2.Auth(key_id, key_secret), args.endpoint, args.bucket)


def upload_release(args: argparse.Namespace, bucket: oss2.Bucket) -> None:
    entry = load_json(args.release_entry)
    release_dir = Path(args.release_dir)
    version = entry["version"]
    for artifact in entry["artifacts"]:
        artifact_path = release_dir / artifact["filename"]
        key = f"{PRODUCT_PREFIX.lstrip('/')}/{version}/{artifact['filename']}"
        put_immutable(bucket, key, artifact_path, "application/zip", artifact["sha256"])
        checksum_path = release_dir / f"{artifact['filename']}.sha256.txt"
        checksum_digest = hashlib.sha256(checksum_path.read_bytes()).hexdigest()
        put_immutable(
            bucket,
            f"{key}.sha256.txt",
            checksum_path,
            "text/plain; charset=utf-8",
            checksum_digest,
        )


def upload_manifest(args: argparse.Namespace, bucket: oss2.Bucket) -> None:
    root = PRODUCT_PREFIX.lstrip("/")
    # The contract intentionally publishes the manifest first and checksum second.
    put_mutable(bucket, f"{root}/manifest.json", Path(args.manifest), "application/json; charset=utf-8")
    put_mutable(
        bucket,
        f"{root}/manifest.json.sha256.txt",
        Path(args.manifest_checksum),
        "text/plain; charset=utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="https://oss-accelerate.aliyuncs.com")
    parser.add_argument("--bucket", default="yaklang")
    subparsers = parser.add_subparsers(dest="command", required=True)
    release = subparsers.add_parser("release")
    release.add_argument("--release-entry", required=True)
    release.add_argument("--release-dir", required=True)
    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--manifest", required=True)
    manifest.add_argument("--manifest-checksum", required=True)
    args = parser.parse_args()

    bucket = make_bucket(args)
    if args.command == "release":
        upload_release(args, bucket)
    else:
        upload_manifest(args, bucket)


if __name__ == "__main__":
    main()
