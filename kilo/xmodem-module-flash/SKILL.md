---
name: xmodem-module-flash
description: Flash or burn SPLC/Octopus-style module firmware images over a selected serial COM port using the bootloader download command and XMODEM-CRC. Use when Codex needs to upgrade CCO, STA, sniffer, listener, or similar module firmware from a .bin image, especially when the user provides a COM port, asks to choose a COM port, mentions 115200 8N1, SecureCRT/460800upgrade.py, bootloader download, or XMODEM serial flashing.
---

# XMODEM Module Flash

Use this skill to flash module firmware through a Windows COM port with the bootloader path validated on the SPLC Octopus modules.

## Required inputs

- Firmware image path (`.bin`). Accept Windows paths, UNC WSL paths, or WSL paths such as `/home/.../image.bin`.
- Target COM port. If the user did not provide it, list ports and ask them to choose before flashing.
- Image slot if known; default to slot `0`.

## Default serial settings

Use `115200 8N1` unless the user or board instructions say otherwise:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <skill>/scripts/flash_xmodem_module.ps1 -FirmwarePath <image.bin> -Port COM6
```

The script opens the selected port, probes for the bootloader, runs `download <slot>`, confirms overwrite with `Y`, transfers the image using XMODEM-CRC, waits for `Image download OK`, and reboots unless `-NoRebootAfter` is set.

## Workflow

1. Resolve the firmware path and verify the file exists.
2. If no COM port was supplied, run `-ListPorts`, show the available ports to the user, and ask which one to use.
3. Run a dry run when validating paths or preparing a command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <skill>/scripts/flash_xmodem_module.ps1 -FirmwarePath <image.bin> -Port COM6 -DryRun
```

4. Run the real flash only after the COM port is confirmed. Preserve the generated log path from script output.
5. Treat success as both XMODEM completion and bootloader confirmation (`Image download OK` or equivalent success text). If either is missing, report the flash as not proven.

## Useful options

- `-ListPorts`: print visible COM ports and exit.
- `-SelfTest`: test CRC-16/XMODEM and packet construction without opening a port.
- `-ImageSlot 1`: use `download 1` instead of `download 0`.
- `-BaudRate 460800 -Parity Even`: override serial settings for boards that require them.
- `-NoRebootAfter`: leave the board in bootloader after flashing.
- `-LogDir <dir>`: choose where the burn log is written.

## Safety rules

- Never claim the board is flashed unless the script reports success.
- Do not use dry-run or self-test output as hardware proof.
- Do not fabricate pass results from logs; include the real command, COM port, image path, and log path in the final report.
- If the port is busy, tell the user which process or terminal likely owns it if known, then retry after it is released.
