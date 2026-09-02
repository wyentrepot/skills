# STA Unity test firmware

Test firmware modifies `/home/H_STA/04/sta` and requires explicit
authorization:

```bash
./bspmake.sh test-create
./bspmake.sh clean
make BSPMAKE_OK=1 AREA=HU_NAN_MODE sta_venus2m test-create
```

The `BSPMAKE_OK` build is required for `UNITY_TEST_FUNC`; a normal STA build
after runner generation is not test firmware. Flash with profile
`sta-v2-hunan-test`, then run:

```powershell
wsl.exe --cd /home/splc_tool/splc-tools/edbg_pc_debug_tool_full_source python3 -m edbg_pc.cli loop test-run --suite all --debug-port <debug-COM> --port <test-log-COM>
```

Use `--suite all`. Compatibility values `phy` and `dll` do not filter this
firmware because it calls `All_tests_main()` at startup. The runtime opens the
test-log port first, reboots through the debug port, saves raw bytes under the
profile evidence folder, and returns `log_path`. It does not send
`dll utest run`. CCO does not support this workflow.
