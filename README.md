# Chrome for Testing ZIP Mirror

这是 Google Chrome for Testing **Stable** 浏览器 ZIP 的下载镜像，适合自动化测试、CI、浏览器驱动程序和需要固定浏览器版本的应用。镜像保留上游 ZIP 的原始内容，不重新打包，也不提供或使用 MSI、DMG、DEB、RPM 等安装包。

Chrome for Testing 不会自动更新。应用应读取 [manifest.json](https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json)，选择平台后下载 ZIP、校验 SHA-256、解压并直接启动其中的浏览器。

> 本镜像与 Google 没有关联或背书。Chrome、Chromium 及相关商标归其各自权利人所有。

## 支持的平台

| 系统 | 架构 | manifest 条件 | ZIP 内的启动路径 |
| --- | --- | --- | --- |
| macOS | Apple Silicon / arm64 | `os == "macos" and arch == "arm64"` | `chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` |
| macOS | Intel / x64 | `os == "macos" and arch == "x64"` | `chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing` |
| Windows | x64 | `os == "windows" and arch == "x64"` | `chrome-win64\chrome.exe` |
| Linux | x64 | `os == "linux" and arch == "x64"` | `chrome-linux64/chrome` |

Google 的 Chrome for Testing 目前只发布 `linux64`、`mac-arm64`、`mac-x64`、`win32` 和 `win64`。上游没有 Windows arm64 或 Linux arm64 的 Chrome ZIP，所以本镜像也不提供这两种包；不会把 x64 文件改名后冒充 arm64。本镜像面向 64 位环境，因此也不收录上游的 Windows 32 位包。可在 [Chrome for Testing 官方支持列表](https://github.com/GoogleChromeLabs/chrome-for-testing#supported-platforms)查看当前上游平台。

## ZIP 中有什么

每个 ZIP 都是可直接解压使用的完整浏览器运行目录，不包含 ChromeDriver，也不是安装程序：

- Linux：`chrome` 主程序、`chrome_sandbox`、ICU 数据、资源包和 `locales/` 等运行文件。
- Windows：`chrome.exe` 主程序、`chrome.dll`、ICU 数据、资源包和 `locales/` 等运行文件。这里的 `chrome.exe` 是浏览器本身，不是安装器。
- macOS：完整的 `Google Chrome for Testing.app`，包括 `Contents/MacOS/` 主程序、`Info.plist`、Frameworks 和 Resources。

不要只复制主程序文件。启动时应保留 ZIP 解压后的整个目录结构。发布检查会对所有 ZIP 做完整性测试，并确认上述入口和关键运行文件存在；之后还会在对应的 Linux、Windows、Intel Mac 和 Apple Silicon Mac 环境中解压并执行浏览器的 `--version`。

## 选择最新版 ZIP

`manifest.json` 是稳定的机器接口。`latest` 是当前 Stable 版本，`versions[0]` 是完整的最新版记录，每个 artifact 都包含 `url`、`sha256`、`size` 和独立的 `checksum_url`。

macOS 或 Linux 示例：

下面的命令需要系统中已有 `curl`、`jq` 和 `shasum`；解压时 macOS 使用系统自带的 `ditto`，Linux 使用 `unzip`。

```bash
manifest_url="https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json"
os="macos"
arch="arm64"

manifest="$(curl -fsSL "$manifest_url")"
version="$(jq -r '.latest' <<<"$manifest")"
url="$(jq -r --arg os "$os" --arg arch "$arch" \
  '.versions[0].artifacts[] | select(.os == $os and .arch == $arch) | .url' <<<"$manifest")"
sha256="$(jq -r --arg os "$os" --arg arch "$arch" \
  '.versions[0].artifacts[] | select(.os == $os and .arch == $arch) | .sha256' <<<"$manifest")"

test -n "$url" && test "$url" != "null"
archive="${url##*/}"
curl -fL --retry 5 -o "$archive" "$url"
printf '%s  %s\n' "$sha256" "$archive" | shasum -a 256 -c -
```

Windows PowerShell 示例：

```powershell
$ManifestUrl = "https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json"
$Manifest = Invoke-RestMethod -Uri $ManifestUrl
$Artifact = $Manifest.versions[0].artifacts |
  Where-Object { $_.os -eq "windows" -and $_.arch -eq "x64" } |
  Select-Object -First 1

if (-not $Artifact) { throw "No Windows x64 Stable ZIP in manifest" }
$Archive = Join-Path $env:TEMP $Artifact.filename
Invoke-WebRequest -Uri $Artifact.url -OutFile $Archive
$ActualHash = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $Artifact.sha256) { throw "SHA-256 mismatch" }
```

manifest 本身也有 [SHA-256 文件](https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json.sha256.txt)。镜像没有额外数字签名，manifest 中的 `signature` 因此为 `null`；SHA-256 能发现内容变化，但不等同于签名身份验证。

## 历史 Stable 大版本

除当前 Stable 和最近更新外，manifest 固定保留下面 5 个历史大版本基线。每个基线都使用该大版本中较新的可用四段版本，并同时满足两个条件：Chrome for Testing 官方历史清单包含全部 4 个镜像平台的 ZIP，Chrome VersionHistory 也确认该版本曾在 Linux、macOS Intel、macOS arm64 和 Windows x64 上进入 Stable。

| Stable 大版本 | 固定版本 | 用途 |
| --- | --- | --- |
| 115 | `115.0.5790.170` | Chrome for Testing 首个正式 Stable 世代 |
| 120 | `120.0.6099.109` | 长期兼容性回归基线 |
| 130 | `130.0.6723.116` | 长期兼容性回归基线 |
| 140 | `140.0.7339.207` | 长期兼容性回归基线 |
| 150 | `150.0.7871.124` | 长期兼容性回归基线 |

下载历史版本时不要使用 `versions[0]`，而应按完整版本号查找：

```bash
version="140.0.7339.207"
os="linux"
arch="x64"

artifact="$(curl -fsSL --compressed \
  https://aliyun-oss.yaklang.com/browsers/chrome/manifest.json | \
  jq -c --arg version "$version" --arg os "$os" --arg arch "$arch" \
    '.versions[] | select(.version == $version) | .artifacts[] |
     select(.os == $os and .arch == $arch)')"
test -n "$artifact"
url="$(jq -r .url <<<"$artifact")"
sha256="$(jq -r .sha256 <<<"$artifact")"
```

根 manifest 最多保留 `max_versions` 条记录；上述 5 条是固定保留项，其余名额用于当前和最近的 Stable 四段版本。因此自动周更不会把这些历史基线淘汰。

## 解压位置与启动方式

建议把版本号放进解压目录。升级时解压到新版本目录，验证成功后再让应用切换路径；不要覆盖正在运行的旧目录。浏览器用户数据应放在解压目录之外，并为并行任务使用不同的 `--user-data-dir`，避免多个进程争用同一份 profile。

### macOS

自动化场景建议解压到：

```text
~/Library/Caches/chrome-for-testing/<version>/
```

解压和确认版本：

```bash
root="$HOME/Library/Caches/chrome-for-testing/$version"
mkdir -p "$root"
ditto -x -k "$archive" "$root"

browser="$root/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
"$browser" --version
```

Intel Mac 把路径中的 `chrome-mac-arm64` 改为 `chrome-mac-x64`。应用自动化时直接执行上述二进制路径；需要按 macOS 应用方式打开时可以使用：

```bash
open -na "$root/chrome-mac-arm64/Google Chrome for Testing.app" --args \
  --user-data-dir="$HOME/Library/Caches/chrome-for-testing/profiles/default"
```

### Linux

自动化和 CI 缓存建议解压到 `${XDG_CACHE_HOME:-$HOME/.cache}/chrome-for-testing/<version>/`：

```bash
root="${XDG_CACHE_HOME:-$HOME/.cache}/chrome-for-testing/$version"
mkdir -p "$root"
unzip -q "$archive" -d "$root"

browser="$root/chrome-linux64/chrome"
"$browser" --version
```

Linux ZIP 包含 Chrome 本身，但主机仍需具备浏览器通常使用的系统共享库。可在目标机器上用 `ldd "$browser"` 检查是否有 `not found`。无界面自动化示例：

```bash
profile="${XDG_CACHE_HOME:-$HOME/.cache}/chrome-for-testing/profiles/job-1"
"$browser" \
  --headless=new \
  --user-data-dir="$profile" \
  --remote-debugging-port=0 \
  about:blank
```

### Windows

建议解压到当前用户的本地应用数据目录，不需要管理员权限：

```text
%LOCALAPPDATA%\ChromeForTesting\<version>\
```

接着前面的 PowerShell 下载示例：

```powershell
$Root = Join-Path $env:LOCALAPPDATA "ChromeForTesting\$($Manifest.latest)"
New-Item -ItemType Directory -Force -Path $Root | Out-Null
Expand-Archive -LiteralPath $Archive -DestinationPath $Root -Force

$Browser = Join-Path $Root "chrome-win64\chrome.exe"
& $Browser --version

$Profile = Join-Path $env:LOCALAPPDATA "ChromeForTesting\profiles\default"
Start-Process -FilePath $Browser -ArgumentList @(
  "--user-data-dir=$Profile",
  "--remote-debugging-port=0",
  "about:blank"
)
```

## 集成建议

应用集成时只需要遵循这一条链路：

1. 获取 `manifest.json`，不要硬编码 `latest` 版本号。
2. 用 `os` 和 `arch` 精确选择一个 artifact；没有匹配项就明确报“不支持”，不要回退到另一种架构。
3. 下载到临时文件，检查 `size` 和 `sha256`。
4. 解压到新的版本目录，并检查上表中的相对启动路径。
5. 执行 `--version`，确认输出包含 manifest 的版本号，再原子切换应用保存的当前版本路径。
6. 启动正式任务时使用独立的 profile 目录；任务结束后由父进程负责关闭浏览器。

同一版本的 ZIP URL 是固定的，适合构建缓存。需要可复现构建时，保存具体 `version` 和 `sha256`；需要始终跟随 Stable 时，每次部署前重新读取 manifest。

## Stable 更新频率

当前 Chrome Stable 的主版本周期约为 4 周，安全和小版本更新通常每周发布，因此具体四段版本号可能在主版本之间变化。从 Chrome 153（计划于 2026 年 9 月 8 日进入 Stable）开始，Google 已宣布 Stable 主版本改为每 2 周一次。发布时间也可能因安全修复或发布调整而变化。

本镜像每天检查一次官方 Stable 元数据，所以正常情况下会在官方发布后的 24 小时内发现新版本。自动任务只跟随当前 Stable；手动任务可以回填明确的四段历史版本，但解析器会同时检查 Chrome for Testing 的 known-good 清单和 Chrome VersionHistory 的全平台 Stable 记录。Beta、Dev、Canary 以及未在全部镜像平台进入过 Stable 的版本都会被拒绝。

参考：[Chrome 发布渠道](https://www.chromium.org/chrome-release-channels/)、[两周发布周期公告](https://developer.chrome.com/blog/chrome-two-week-release/)、[Chrome for Testing](https://developer.chrome.com/blog/chrome-for-testing/)、[Chrome VersionHistory API](https://developer.chrome.com/docs/web-platform/versionhistory/reference)。
