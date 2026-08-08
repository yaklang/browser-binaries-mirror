#!/usr/bin/env python3
"""Download, extract, and execute one native browser ZIP from the public mirror."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from mirrorlib import PRODUCT_PREFIX, executable_path, sha256_file, validate_zip_layout


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "browser-binaries-mirror-runtime/1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
        if response.headers.get("Content-Encoding", "").lower() == "gzip":
            data = gzip.decompress(data)
        return json.loads(data)


def extract_zip(archive: Path, destination: Path) -> None:
    if os.name == "nt":
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(destination)
    elif os.uname().sysname == "Darwin":
        subprocess.run(["ditto", "-x", "-k", str(archive), str(destination)], check=True)
    else:
        subprocess.run(["unzip", "-q", str(archive), "-d", str(destination)], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--os", required=True, choices=("linux", "macos", "windows"))
    parser.add_argument("--arch", required=True, choices=("arm64", "x64"))
    args = parser.parse_args()

    manifest_url = f"{args.public_base_url.rstrip('/')}{PRODUCT_PREFIX}/manifest.json"
    manifest = fetch_json(manifest_url)
    latest = manifest["versions"][0]
    matches = [
        artifact
        for artifact in latest["artifacts"]
        if artifact["os"] == args.os and artifact["arch"] == args.arch
    ]
    if len(matches) != 1:
        raise ValueError(f"latest Stable has no unique ZIP for {args.os}/{args.arch}")
    artifact = matches[0]

    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        archive = temp_dir / artifact["filename"]
        subprocess.run(
            [
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--location",
                "--retry",
                "5",
                "--retry-all-errors",
                "--output",
                str(archive),
                artifact["url"],
            ],
            check=True,
        )
        if archive.stat().st_size != artifact["size"]:
            raise ValueError("downloaded ZIP size does not match the manifest")
        if sha256_file(archive) != artifact["sha256"]:
            raise ValueError("downloaded ZIP SHA-256 does not match the manifest")
        validate_zip_layout(archive, artifact)

        extracted = temp_dir / "extracted"
        extracted.mkdir()
        extract_zip(archive, extracted)
        browser = extracted / executable_path(args.os, args.arch)
        if not browser.is_file():
            raise ValueError(f"documented browser path was not extracted: {browser}")
        result = subprocess.run(
            [str(browser), "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        version_output = f"{result.stdout}\n{result.stderr}".strip()
        if latest["version"] not in version_output:
            raise ValueError(
                f"extracted browser did not report Stable {latest['version']}: {version_output!r}"
            )
        print(f"verified {args.os}/{args.arch}: {version_output}")


if __name__ == "__main__":
    main()
