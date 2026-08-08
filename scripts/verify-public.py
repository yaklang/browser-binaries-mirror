#!/usr/bin/env python3
"""Verify public CDN headers, manifest contract, sizes, and actual SHA-256s."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import re
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode, urlsplit, urlunsplit

from mirrorlib import PRODUCT_PREFIX, load_json, load_schema_and_validate, sha256_file, validate_release_entry


def cache_bust(url: str) -> str:
    parts = urlsplit(url)
    query = parts.query + ("&" if parts.query else "") + urlencode({"mirror_verify": time.time_ns()})
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))


def request(url: str, method: str = "GET", attempts: int = 5):
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(
                cache_bust(url), method=method, headers={"User-Agent": "browser-binaries-mirror-verifier/1"}
            )
            return urllib.request.urlopen(req, timeout=60)
        except Exception as exc:  # noqa: BLE001 - retry network and transient CDN failures
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"{method} {url} failed after {attempts} attempts: {last_error}")


def get_bytes(url: str) -> bytes:
    with request(url) as response:
        return response.read()


def head(url: str) -> dict[str, str]:
    with request(url, method="HEAD") as response:
        if response.status != 200:
            raise RuntimeError(f"HEAD {url} returned HTTP {response.status}")
        return {key.lower(): value for key, value in response.headers.items()}


def require_headers(headers: dict[str, str], *, kind: str, expected_size: int | None = None) -> None:
    if int(headers.get("content-length", "-1")) <= 0:
        raise ValueError(f"{kind} Content-Length is missing or empty")
    if expected_size is not None and int(headers.get("content-length", "-1")) != expected_size:
        raise ValueError(f"{kind} Content-Length mismatch")
    content_type = headers.get("content-type", "").lower()
    cache_control = headers.get("cache-control", "").lower()
    if kind == "zip":
        if "application/zip" not in content_type:
            raise ValueError(f"ZIP Content-Type mismatch: {content_type!r}")
        if "max-age=31536000" not in cache_control or "immutable" not in cache_control:
            raise ValueError(f"ZIP Cache-Control mismatch: {cache_control!r}")
    elif kind == "checksum":
        if "text/plain" not in content_type:
            raise ValueError(f"checksum Content-Type mismatch: {content_type!r}")
    elif kind == "manifest":
        if "application/json" not in content_type:
            raise ValueError(f"manifest Content-Type mismatch: {content_type!r}")
        if "max-age=300" not in cache_control or "must-revalidate" not in cache_control:
            raise ValueError(f"manifest Cache-Control mismatch: {cache_control!r}")
    if kind == "checksum":
        # Both version and root checksum policies contain max-age; validate either exact contract.
        if not (
            ("max-age=31536000" in cache_control and "immutable" in cache_control)
            or ("max-age=300" in cache_control and "must-revalidate" in cache_control)
        ):
            raise ValueError(f"checksum Cache-Control mismatch: {cache_control!r}")


def parse_checksum(data: bytes, filename: str) -> str:
    text = data.decode("utf-8").strip()
    match = re.fullmatch(r"([0-9a-f]{64})  (.+)", text)
    if not match or match.group(2) != filename:
        raise ValueError(f"invalid checksum document for {filename}: {text!r}")
    return match.group(1)


def verify_artifact_headers(artifact: dict) -> None:
    require_headers(head(artifact["url"]), kind="zip", expected_size=artifact["size"])
    require_headers(head(artifact["checksum_url"]), kind="checksum")
    published_sha = parse_checksum(get_bytes(artifact["checksum_url"]), artifact["filename"])
    if published_sha != artifact["sha256"]:
        raise ValueError(f"published checksum mismatch for {artifact['filename']}")


def download_and_hash(artifact: dict) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        target = Path(temp_dir) / artifact["filename"]
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--retry",
                "5",
                "--retry-all-errors",
                "--output",
                str(target),
                cache_bust(artifact["url"]),
            ],
            check=True,
        )
        if target.stat().st_size != artifact["size"] or sha256_file(target) != artifact["sha256"]:
            raise ValueError(f"actual public content mismatch for {artifact['filename']}")


def verify_release(entry: dict, download: bool) -> None:
    validate_release_entry(entry)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(verify_artifact_headers, entry["artifacts"]))
    if download:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(download_and_hash, entry["artifacts"]))


def verify_manifest(public_base_url: str, schema: str, download_latest: bool) -> None:
    manifest_url = f"{public_base_url.rstrip('/')}{PRODUCT_PREFIX}/manifest.json"
    checksum_url = f"{manifest_url}.sha256.txt"
    require_headers(head(manifest_url), kind="manifest")
    require_headers(head(checksum_url), kind="checksum")

    manifest_bytes = b""
    for attempt in range(5):
        manifest_bytes = get_bytes(manifest_url)
        published_sha = parse_checksum(get_bytes(checksum_url), "manifest.json")
        if hashlib.sha256(manifest_bytes).hexdigest() == published_sha:
            break
        if attempt == 4:
            raise ValueError("manifest SHA-256 did not converge after publication retry window")
        time.sleep(2**attempt)

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "manifest.json"
        path.write_bytes(manifest_bytes)
        manifest = load_json(path)
    load_schema_and_validate(manifest, schema)
    expected_prefix = f"{public_base_url.rstrip('/')}{PRODUCT_PREFIX}/"
    for version in manifest["versions"]:
        for artifact in version["artifacts"]:
            if not artifact["url"].startswith(expected_prefix) or not artifact["checksum_url"].startswith(
                expected_prefix
            ):
                raise ValueError(f"manifest URL is outside configured public base: {artifact['url']}")
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(verify_artifact_headers, [a for v in manifest["versions"] for a in v["artifacts"]]))
    if download_latest:
        verify_release(manifest["versions"][0], download=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-base-url", default="https://aliyun-oss.yaklang.com")
    parser.add_argument("--schema", default="schemas/manifest.schema.json")
    parser.add_argument("--release-entry")
    parser.add_argument("--download-latest", action="store_true")
    args = parser.parse_args()
    if args.release_entry:
        verify_release(load_json(args.release_entry), download=False)
    else:
        verify_manifest(args.public_base_url, args.schema, args.download_latest)


if __name__ == "__main__":
    main()
