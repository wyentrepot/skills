# Cross-project validation and packaging

Check the C field/getter/runtime branch, Python `ctypes`/serializer/parser,
upper-host load/reset/edit/save/display paths, Qt source/generated UI, every
affected province JSON, layout/default/enabled/disabled/round-trip/UI tests, and
embedded packers. JSON must have no comments or trailing commas.

Run upper-host tests from its root:

```bash
python3 -m pytest -q
python3 -m json.tool path/to/scheme.json >/dev/null
git diff --check
```

Rebuild Linux packers from `tools/build.sh`, then copy `tools/dist/verpackcli`
and `verunpackcli` into firmware `make/versionmanager/`. Resolve source merge
conflicts before regenerating binaries; never choose a conflicted binary side.

Build representative enabled/disabled regions. Firmware build prompts can
consume following commands, so redirect stdin from `/dev/null` or run commands
separately. Clean before every change of `AREA`, and clean when the existing
object provenance is unknown. Treat an incremental build after a region switch
as invalid even if it succeeds. Clean again before the final target-region
build. Use `git -c core.whitespace=cr-at-eol diff --check` for firmware and
preserve existing CRLF.

When the user waives testing, interpret the waiver narrowly, record it, and
remove those checks from the remaining plan immediately. Reuse still-valid
evidence while its inputs are unchanged; run only non-waived contract, build,
packaging, or hardware checks unless the user later expands the scope.

Rebuild and smoke-test the separate Windows PyInstaller package for changed UI,
parser, or delivery. Windows may read WSL sources by UNC path, but mutate
`/home` only through the default WSL environment under `wsl-safe-writing`.
