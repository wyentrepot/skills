# STA firmware and upper-host binary contract

Firmware is `/home/H_STA/04/sta`; the upper host is
`/home/H_STA/py_manage/moduleparasconfigtool` with entry point `mainRun.py`.

| Concern | Firmware | Upper host |
|---|---|---|
| Footer/flags | `protocol/aps/inc/version_manager.h` | `utils/attachment.py` |
| Runtime/display | `protocol/aps/src/version_manager.c` | `utils/upgFileDo.py`, `myToolGUI.py` |
| Defaults | `make/versionmanager/*.json` | root and `resources/*.json` |
| UI | N/A | `ui/config.ui`, generated `ui/config.py` |
| Packers | `make/versionmanager/verpackcli`, `verunpackcli` | `tools/dist/` |

- Compare C and Python `ctypes` packed structures field by field, including
  nested structures, reserve bits, and total size.
- The footer is 76 bytes and includes a four-byte JZJC compatibility field
  after LED configuration; do not use the old 72-byte layout.
- Preserve bit positions. A display-name change need not rename or move the
  internal field.
- Define absent-key and invalid/legacy-footer behavior.
- Parse the actual final footer to validate artifacts.
- Bit 7 remains internal `assoc_enhance_en`, defaults enabled for old schemes,
  and is disabled by the Anhui scheme.
