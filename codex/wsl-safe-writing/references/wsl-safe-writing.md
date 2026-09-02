# WSL Safe-Writing Command Guide

Use this workflow only to prevent cross-filesystem corruption in a user-authorized WSL development environment. It does not bypass or disable enterprise DLP, anti-leak, or encryption controls.

Windows may inspect WSL-native files read-only. Every write and Git state change must run inside the current default WSL. Never detect, select, or hardcode a distribution.

## Reliable PowerShell-to-WSL execution

PowerShell 5 can remove nested quotes from native-program arguments, while text pipelines can add CRLF line endings. Avoid both problems by Base64-encoding the complete Bash script in Windows memory:

```powershell
function Invoke-DefaultWslScript {
    param([Parameter(Mandatory)][string]$Script)

    $normalized = $Script -replace "`r`n", "`n"
    $script64 = [Convert]::ToBase64String(
        [Text.Encoding]::UTF8.GetBytes($normalized)
    )
    $launcher = "printf '%s' '$script64' | base64 --decode | bash"
    wsl -e bash -c $launcher
    if ($LASTEXITCODE -ne 0) {
        throw "WSL script failed with exit code $LASTEXITCODE"
    }
}
```

The script and its data stay in memory until WSL executes them. Windows creates no plaintext temporary file and never opens the WSL target.

## Encode values before embedding them

Paths and user-controlled values must not be interpolated as raw shell text. Encode each value:

```powershell
function ConvertTo-Utf8Base64([string]$Value) {
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Value))
}
```

Decode values inside Bash with `printf '%s' 'BASE64' | base64 --decode`.

## Create a UTF-8 multiline file

```powershell
$target64 = ConvertTo-Utf8Base64 '/home/me/project/config.toml'
$content64 = ConvertTo-Utf8Base64 @'
# Example configuration
name = "demo"
message = "UTF-8 text: 安全写入"
'@

$script = @"
set -euo pipefail
target=`$(printf '%s' '$target64' | base64 --decode)
printf '%s' '$content64' | base64 --decode > "`$target"
"@
Invoke-DefaultWslScript $script
```

## Make a small deterministic edit

Require exactly one expected match before changing it:

```powershell
$file64 = ConvertTo-Utf8Base64 '/home/me/project/src/config.c'
$old64 = ConvertTo-Utf8Base64 '#define TIMEOUT 10'
$new64 = ConvertTo-Utf8Base64 '#define TIMEOUT 30'

$script = @"
set -euo pipefail
file=`$(printf '%s' '$file64' | base64 --decode)
old=`$(printf '%s' '$old64' | base64 --decode)
new=`$(printf '%s' '$new64' | base64 --decode)
count=`$(grep -Fxc -- "`$old" "`$file")
test "`$count" -eq 1
OLD="`$old" NEW="`$new" python3 - "`$file" <<'PY'
import os, pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
old, new = os.environ["OLD"], os.environ["NEW"]
if text.count(old) != 1:
    raise SystemExit("expected exactly one match")
p.write_text(text.replace(old, new), encoding="utf-8")
PY
"@
Invoke-DefaultWslScript $script
```

For structured transformations, use a parser inside WSL rather than a blind replacement.

## Apply an existing patch inside WSL

```powershell
$repo64 = ConvertTo-Utf8Base64 '/home/me/project'
$patch64 = ConvertTo-Utf8Base64 '/home/me/patches/fix.patch'
$script = @"
set -euo pipefail
repo=`$(printf '%s' '$repo64' | base64 --decode)
patch=`$(printf '%s' '$patch64' | base64 --decode)
cd "`$repo"
git apply --check "`$patch"
git apply "`$patch"
"@
Invoke-DefaultWslScript $script
```

For traditional patches, run `patch --dry-run` before `patch`. Never use Windows `apply_patch` against a WSL-native target.

## Filesystem, formatting, generation, and Git mutations

Execute the operation-specific tool inside the decoded WSL script. This includes creating, moving, deleting, formatting, generating, staging, restoring, checking out, committing, rebasing, and merging.

Example Git mutation:

```powershell
$repo64 = ConvertTo-Utf8Base64 '/home/me/project'
$file64 = ConvertTo-Utf8Base64 'src/config.c'
$message64 = ConvertTo-Utf8Base64 'Set timeout to 30'
$script = @"
set -euo pipefail
repo=`$(printf '%s' '$repo64' | base64 --decode)
file=`$(printf '%s' '$file64' | base64 --decode)
message=`$(printf '%s' '$message64' | base64 --decode)
cd "`$repo"
git add -- "`$file"
git diff --cached --check
git commit -m "`$message"
"@
Invoke-DefaultWslScript $script
```

Only commit when the user has authorized a commit.

## Verify readable plaintext

```powershell
$file64 = ConvertTo-Utf8Base64 '/home/me/project/src/config.c'
$script = @"
set -euo pipefail
file=`$(printf '%s' '$file64' | base64 --decode)
test ! -s "`$file" || grep -Iq . "`$file"
iconv -f UTF-8 -t UTF-8 "`$file" >/dev/null
sed -n '1,40p' "`$file"
"@
Invoke-DefaultWslScript $script
```

For intentionally non-UTF-8 text, use the repository's declared encoding. For binary artifacts, use the artifact-specific validator.

## Run the relevant check

```powershell
$repo64 = ConvertTo-Utf8Base64 '/home/me/project'
$script = @"
set -euo pipefail
repo=`$(printf '%s' '$repo64' | base64 --decode)
cd "`$repo"
make test
make
"@
Invoke-DefaultWslScript $script
```

Choose the narrowest relevant unit test, linter, compiler check, build, or cross-compilation target. A successful write without relevant WSL-side validation is incomplete.

## Recover from a polluted file

If a file is garbled, contains unexpected bytes, produces `invalid source character`, or causes unexplained cross-compilation failures:

1. Stop all writes. Do not attempt a Windows-side repair.
2. Inside WSL, capture `git status --short`, `file`, `sha256sum`, and `xxd -l 64`.
3. Determine whether uncommitted work must be preserved. Do not overwrite unknown user changes.
4. With user authorization, restore a tracked file from a known clean revision using WSL Git.
5. Regenerate untracked or generated files through the safe workflow.
6. Repeat plaintext verification and the relevant test, static check, or build.

If WSL execution, decoding, writing, verification, or validation fails, stop and report the exact failure. Never fall back to a Windows-side writer.
