# Runtime, profiles, and verification

Runtime: `/home/splc_tool/splc-tools/edbg_pc_debug_tool_full_source/`.
WSL invokes PowerShell, Windows Python, then the COM port. Evidence and settings
are stored in the WSL-native archive:

- WSL: `/d/<sta|cco>/<project-name>/`
- Windows view: `\\wsl.localhost\Ubuntu-22.04\d\<sta|cco>\<project-name>\`

The project name is `<parent>-<project>`. Do not create new logs or settings on
`D:`. Existing `D:\11-ai-workfile` files are legacy archives and are not
migrated or deleted automatically.

Settings are `readme-<profile-id>.txt` in that folder. Normal and Unity STA
settings never share values. A non-test profile may migrate legacy `readme.txt`
only when its profile file is absent; the test profile never migrates it.
Before confirmation, present saved `project_root`, `profile_id`,
`build_command`, `latest_firmware`, `port`, `baud`, `packet_size`, and available
identity fields. Treat differences as proposals. The runtime updates only the
selected profile after successful transfer; failed flash and standalone
capture/grab must not update settings.

New `/d` settings are plaintext on the WSL-native filesystem. For legacy
encrypted `D:` settings or unavailable shell reads, use runtime-returned
`readme` and `updated_readme` as the authoritative comparison. Normal STA must
not retain `test-create`; test STA must not inherit a normal build command. A
transfer may succeed while settings synchronization fails, so report those
outcomes separately.

Before building, perform one bounded preflight:

- Verify the WSL CLI can reach the Windows worker and its Python imports without
  opening a transfer.
- Enumerate the confirmed COM port and check known serial terminals/processes
  for occupancy. Require release before flashing.
- From WSL, create, read back, and remove one exact canary under the selected
  `/d/...` archive root. Stop if it is not plaintext.
- Never copy raw `readme-*.txt` bytes from a Windows worker temp directory into
  WSL; DLP may encrypt them. Persist settings inside WSL from authoritative
  `updated_readme` fields.

| Property | STA | CCO |
|---|---|---|
| Profile | `sta-v2-hunan` | `cco-hunan` |
| Project | `/home/H_STA/04/sta` | `/home/H_CCO/001/cco` |
| Target | venus2m | venus8m |
| Build | `./bspmake.sh HU_NAN sta_venus2m` | `make jump` |
| Artifact | `firmware/sta_venus2m/iap_sta_venus2m*.bin` | `firmware/iap_cco_*.bin` |
| Packet | 1024 bytes | 1024 bytes |
| Baud | 115200 then 460800 | 115200 |
| Pre-download | none | `setmode 0` |

Both STA normal and Unity-test profiles must use 1024-byte packets. Treat a
saved or runtime value of 128 as stale and stop before transfer.

The runtime enters bootloader after its prompt; do not spam keys. A successful
normal flash returns `ok`, `version`, `diqu`, `evidence`, `serial_log`, and
`readme_path`/`updated_readme`. It waits for `[node /]$`, sends `version`, and parses
`sversion` plus `diqu name`. A successful transfer may have a verification
`warning`; report transfer success and incomplete application verification
separately.

The STA test profile returns empty normal version/region plus
`firmware_identity` (`hversion`, `sver`, `isv`) and a
`test_firmware_identity` verification object. Report identity separately from
the later Unity result.

Known caveats:

- CCO `doctor` falsely checks a project file named `make`; verify `Makefile` and
  the PATH command separately.
- CCO profile's `COM11` default is unsafe; always pass the confirmed port.
- `loop run` has no port option; do not use it for CCO.
- CLI help says flash is unverified, but current `flash_only()` verifies.
