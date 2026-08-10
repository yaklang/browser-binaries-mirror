#!/usr/bin/env python3
"""Resolve current or explicitly requested historical Stable CfT ZIPs."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from mirrorlib import (
    KNOWN_GOOD_MANIFEST_URL,
    PLATFORMS,
    SOURCE_MANIFEST_URL,
    VERSION_HISTORY_URL,
    artifact_url,
    version_key,
    write_json,
)

STABLE_HISTORY_PLATFORMS = {"linux", "mac", "mac_arm64", "win64"}
VERSION_HISTORY_NAME_RE = re.compile(
    r"^chrome/platforms/([^/]+)/channels/stable/versions/(\d+\.\d+\.\d+\.\d+)$"
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


def current_stable(metadata: dict[str, Any]) -> dict[str, Any]:
    stable = metadata.get("channels", {}).get("Stable")
    if not isinstance(stable, dict):
        raise ValueError("official metadata does not contain channels.Stable")
    return stable


def stable_history_url(version: str) -> str:
    query = urllib.parse.urlencode({"filter": f"version={version}", "page_size": "1000"})
    return f"{VERSION_HISTORY_URL}?{query}"


def stable_history_platforms(metadata: dict[str, Any], version: str) -> set[str]:
    platforms: set[str] = set()
    for item in metadata.get("versions", []):
        if not isinstance(item, dict) or item.get("version") != version:
            continue
        match = VERSION_HISTORY_NAME_RE.fullmatch(str(item.get("name", "")))
        if match and match.group(2) == version:
            platforms.add(match.group(1))
    return platforms


def select_release(
    current_metadata: dict[str, Any],
    requested_version: str | None,
    known_good_metadata: dict[str, Any] | None = None,
    stable_history_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stable = current_stable(current_metadata)
    if not requested_version or requested_version == stable.get("version"):
        return stable

    version_key(requested_version)
    if known_good_metadata is None or stable_history_metadata is None:
        raise ValueError("historical version resolution requires CfT and Stable history metadata")

    matches = [
        item
        for item in known_good_metadata.get("versions", [])
        if isinstance(item, dict) and item.get("version") == requested_version
    ]
    if len(matches) != 1:
        raise ValueError(f"requested version {requested_version} is not a known-good CfT version")

    stable_platforms = stable_history_platforms(stable_history_metadata, requested_version)
    missing = sorted(STABLE_HISTORY_PLATFORMS - stable_platforms)
    if missing:
        raise ValueError(
            f"requested version {requested_version} was not Stable on every mirrored platform; "
            f"missing {missing}"
        )
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--version",
        help="exact current or historical Stable four-part version; defaults to current Stable",
    )
    parser.add_argument("--metadata-file", help="local official metadata fixture")
    parser.add_argument("--public-base-url", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    metadata_url = SOURCE_MANIFEST_URL
    if args.metadata_file:
        with open(args.metadata_file, encoding="utf-8") as handle:
            metadata = json.load(handle)
    else:
        metadata = fetch_json(metadata_url)
    known_good_metadata = None
    stable_history_metadata = None
    resolved_from = metadata_url
    if args.version and args.version != current_stable(metadata).get("version"):
        known_good_metadata = fetch_json(KNOWN_GOOD_MANIFEST_URL)
        history_url = stable_history_url(args.version)
        stable_history_metadata = fetch_json(history_url)
        resolved_from = KNOWN_GOOD_MANIFEST_URL
    selected = select_release(
        metadata,
        args.version,
        known_good_metadata=known_good_metadata,
        stable_history_metadata=stable_history_metadata,
    )
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
            raise ValueError(f"official Stable metadata lacks chrome ZIP for {upstream_platform}")
        if not source_url.endswith(".zip"):
            raise ValueError(f"official Stable artifact for {upstream_platform} is not a ZIP")
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
            "resolved_from": resolved_from,
            "artifacts": artifacts,
        },
    )


if __name__ == "__main__":
    main()
