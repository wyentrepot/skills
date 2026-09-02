---
name: wsl-safe-writing
description: Use only when mutating files on the WSL-native Linux filesystem, such as paths under `/home`, `/etc`, or `/var`, especially where DLP or anti-leak encryption may corrupt cross-environment writes. Do not use for Windows-native paths (`C:\...`, `%USERPROFILE%`, `.codex` skills/plugins) or Windows drives mounted under `/mnt`; use Windows tools directly for those targets.
---

# WSL Safe Writing

## Overview

Keep WSL-native content readable by separating inspection from mutation. Windows-side tools may only inspect WSL files read-only; every filesystem or Git mutation affecting WSL-native content MUST execute inside the current default WSL environment.

## Scope Gate

- Use this workflow only for the WSL distribution's native Linux filesystem.
- Do not use it for `C:\...`, `%USERPROFILE%`, `.codex`, `AppData`, or `/mnt/<drive>/...`.
- Install Windows Codex skills and plugins entirely with Windows tools.

## Required Workflow

1. Inspect from Windows only when the operation is read-only.
2. Run every mutation through the current default WSL. From Windows PowerShell, UTF-8/Base64 encode the Bash script in memory and let WSL decode and execute it; this avoids PowerShell native-argument quote loss and CRLF pollution. Never detect, select, or hardcode a distribution.
3. Select the WSL-native mutation method:

| Task | Required method |
|---|---|
| Small deterministic edit | WSL `python3`, `sed`, or another Linux tool |
| New or complex multiline content | Encode UTF-8 content to Base64 in Windows memory, pipe it to WSL, and decode there |
| Existing patch | Run `git apply`, `patch`, or another patch tool inside WSL |
| Stage, commit, move, delete, format, or generate | Run the relevant filesystem or Git command inside WSL |

4. After writing, verify readable plaintext inside WSL.
5. Run the relevant test, static check, or build inside WSL.

If WSL execution, Base64 decoding, writing, plaintext verification, or validation fails, stop and report the failure. Never fall back to Windows-side writing.

## Prohibited Mutation Paths

Do not mutate WSL-native targets with Windows `apply_patch`, PowerShell file-writing or redirection, Windows Python file APIs, editor saves, or Windows temporary plaintext files. A Windows process creating content in memory does not authorize it to write the target or a plaintext transfer file.

## Red Flags

- A command writes through `\\wsl$`, `\\wsl.localhost`, or a Windows-mounted view of the target.
- A fallback uses a Windows editor, script, redirection, or patch tool.
- Verification stops after the mutation command.
- Git staging or committing is planned from Windows.

Stop and reformulate the operation as a default-WSL command whenever any red flag appears.

## Detailed Commands and Recovery

Read [references/wsl-safe-writing.md](references/wsl-safe-writing.md) before choosing exact commands, transferring multiline content, applying patches, performing Git mutations, verifying output, or recovering a polluted file.
