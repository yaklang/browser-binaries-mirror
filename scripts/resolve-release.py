#!/usr/bin/env python3
"""Resolve the official Stable Chrome for Testing release and four ZIPs."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any

from mirrorlib import (
    KNOWN_GOOD_MANIFEST_URL,
    PLATFORMS,
    SOURCE_MANIFEST_URL,
    artifact_url,
    version_key,
    write_json,
)


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "browser-binaries-mirror/1"})
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except Exception as exc:  # noqa: BLE001 - preserve network error context
            last_error = exc
            if attempt < 4:
                time.sleep(2**attempt)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def select_release(metadata: dict[str, Any], requested_version: str | None) -> dict[str, Any]:
    if requested_version:
        version_key(requested_version)
        matches = [item for item in metadata.get("versions", []) if item.get("version") == requested_version]
        if len(matches) != 1:
            raise ValueError(f"version {requested_version} was not found exactly once in official metadata")
        return matches[0]
    stable = metadata.get("channels", {}).get("Stable")
    if not isinstance(stable, dict):
        raise ValueError("official metadata does not contain channels.Stable")
    return stable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="exact official four-part version to backfill")
    parser.add_argument("--metadata-file", help="local official metadata fixture")
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metadata_url = KNOWN_GOOD_MANIFEST_URL if args.version else SOURCE_MANIFEST_URL
    if args.metadata_file:
        with open(args.metadata_file, encoding="utf-8") as handle:
            metadata = json.load(handle)
    else:
        metadata = fetch_json(metadata_url)
    selected = select_release(metadata, args.version)
    version = selected.get("version")
    version_key(version)
    revision = str(selected.get("revision", ""))
    if not revision.isdigit():
        raise ValueError(f"invalid Chromium revision: {revision!r}")

    chrome_downloads = selected.get("downloads", {}).get("chrome", [])
    downloads_by_platform = {item.get("platform"): item.get("url") for item in chrome_downloads}
    artifacts = []
    for upstream_platform, os_name, arch in PLATFORMS:
        source_url = downloads_by_platform.get(upstream_platform)
        if not isinstance(source_url, str):
            raise ValueError(f"official metadata lacks chrome download for {upstream_platform}")
        filename = f"chrome-cft-{version}-{os_name}-{arch}.zip"
        url = artifact_url(args.public_base_url, version, filename)
        artifacts.append(
            {
                "os": os_name,
                "arch": arch,
                "format": "zip",
                "filename": filename,
                "url": url,
                "checksum_url": f"{url}.sha256.txt",
                "source_url": source_url,
                "signature": None,
            }
        )
    write_json(
        args.output,
        {
            "version": version,
            "revision": revision,
            "channel": "stable",
            "resolved_from": metadata_url,
            "artifacts": artifacts,
        },
    )


if __name__ == "__main__":
    main()
