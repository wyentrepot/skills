# Runtime troubleshooting

| Symptom | Check |
|---|---|
| Serial port cannot open | Port absent, occupied, or board disconnected |
| `Download failed: -3` | Bootloader/X-Modem handshake timing |
| `Xmodem Download failed: -2` | Interrupted transfer or packet-size mismatch; STA and CCO V2 require 1024 |
| `Image download failed!` | CCO 1024-byte packets and `setmode 0` |
| Bootloader not entered | Key window missed; do not spam before prompt |
| Capture timeout | Wrong keyword, silent board, or short timeout |
| Verification warning | Inspect bounded serial context; transfer and boot differ |
