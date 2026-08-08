# Chrome for Testing OSS Mirror

This repository mirrors the official Google Chrome for Testing **Stable** channel to Yaklang's public Aliyun OSS domain. Chrome for Testing is intended for browser automation and testing; it is not a normal end-user browser update channel.

The mirror republishes the upstream ZIPs without changing their contents. It is not affiliated with or endorsed by Google. Chrome, Chromium, and related trademarks belong to their respective owners.

## Manifest

- [manifest.json](https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json)
- [manifest.json.sha256.txt](https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json.sha256.txt)

The manifest is the source of truth for the current version and download URLs. It retains the latest 10 completely published versions by default.

## Latest Stable downloads

At project launch, the official Stable release is `151.0.7922.77`. Use the manifest links below after the first mirror run; clients should read `manifest.json` rather than hard-code this version.

| Platform | Architecture | Package | SHA-256 |
| --- | --- | --- | --- |
| macOS | arm64 | [ZIP](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-macos-arm64.zip) | [checksum](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-macos-arm64.zip.sha256.txt) |
| macOS | x64 | [ZIP](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-macos-x64.zip) | [checksum](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-macos-x64.zip.sha256.txt) |
| Windows | x64 | [ZIP](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-windows-x64.zip) | [checksum](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-windows-x64.zip.sha256.txt) |
| Linux | x64 | [ZIP](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-linux-x64.zip) | [checksum](https://aliyun-oss.yaklang.com/browsers/chrome/151.0.7922.77/chrome-cft-151.0.7922.77-linux-x64.zip.sha256.txt) |

Get a platform URL from the live manifest:

```bash
curl -fsSL "https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json" \
  | jq -r '.versions[0].artifacts[] | select(.os == "macos" and .arch == "arm64") | .url'
```

## Object layout

```text
/browsers/chrome/
├── manifest.json
├── manifest.json.sha256.txt
├── 151.0.7922.77/
│   ├── chrome-cft-151.0.7922.77-macos-arm64.zip
│   ├── chrome-cft-151.0.7922.77-macos-arm64.zip.sha256.txt
│   ├── chrome-cft-151.0.7922.77-macos-x64.zip
│   ├── chrome-cft-151.0.7922.77-macos-x64.zip.sha256.txt
│   ├── chrome-cft-151.0.7922.77-windows-x64.zip
│   ├── chrome-cft-151.0.7922.77-windows-x64.zip.sha256.txt
│   ├── chrome-cft-151.0.7922.77-linux-x64.zip
│   └── chrome-cft-151.0.7922.77-linux-x64.zip.sha256.txt
└── <older-version>/
    └── ...
```

Versioned objects are immutable. If an object already exists, the publisher checks its byte size and stored SHA-256 metadata. A mismatched object fails the release instead of being overwritten. Removing an older entry from the bounded manifest does not delete its OSS objects.

## Download and verify

macOS or Linux:

```bash
version="$(curl -fsSL https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json | jq -r .latest)"
filename="chrome-cft-${version}-macos-arm64.zip"
base="https://aliyun-oss.yaklang.com/browsers/chrome/${version}"

curl -fLO "${base}/${filename}"
curl -fLO "${base}/${filename}.sha256.txt"
shasum -a 256 -c "${filename}.sha256.txt"
```

Windows PowerShell:

```powershell
Get-FileHash .\chrome-cft-${version}-windows-x64.zip -Algorithm SHA256
```

Verify the manifest itself:

```bash
curl -fLO https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json
curl -fLO https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json.sha256.txt
shasum -a 256 -c manifest.json.sha256.txt
```

## Signing and integrity

Signing status: **unsigned by this mirror project**.

Integrity: SHA-256 checksums are published for the manifest and every artifact. SHA-256 checksums detect content changes, but they are not digital signatures. Each manifest artifact therefore has `"signature": null` in schema version 1.

## Automation

[`mirror.yml`](.github/workflows/mirror.yml) runs every six hours and can also be dispatched for an exact official four-part version. It:

1. resolves Google Chrome for Testing metadata;
2. downloads and ZIP-tests all four upstream packages;
3. computes hashes and uploads through the OSS acceleration endpoint;
4. verifies every new object through `aliyun-oss.yaklang.com`;
5. merges, sorts, deduplicates, and bounds the manifest;
6. publishes the manifest followed by its checksum; and
7. performs a complete public download and SHA-256 check of the latest release.

The manifest is updated only after all platform objects are uploaded and publicly reachable. A failed platform cannot create a partial manifest release.

[`verify.yml`](.github/workflows/verify.yml) runs contract tests on pushes and pull requests. Its daily and manual production smoke test checks response headers and sizes for every indexed object, validates the manifest schema and checksum, and downloads every latest-version artifact to verify its real content.

### Required GitHub Actions configuration

Secrets:

- `OSS_KEY_ID`: an Aliyun identity restricted to the `browsers/chrome/*` prefix.
- `OSS_KEY_SECRET`: the corresponding secret.

Optional repository variables:

- `PUBLIC_BASE_URL` (default `https://aliyun-oss.yaklang.com`)
- `MANIFEST_MAX_VERSIONS` (default `10`)

Upload settings are intentionally fixed to Bucket `yaklang` and endpoint `https://oss-accelerate.aliyuncs.com`. Public validation uses the custom accelerated domain, not the authenticated upload endpoint.

## Upstream

- [Chrome for Testing overview](https://developer.chrome.com/blog/chrome-for-testing/)
- [Chrome for Testing availability](https://googlechromelabs.github.io/chrome-for-testing/)
- [Official version metadata repository](https://github.com/GoogleChromeLabs/chrome-for-testing)
