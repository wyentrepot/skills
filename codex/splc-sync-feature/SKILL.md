---
name: splc-sync-feature
description: Synchronize one named feature across the SPLC STA firmware at /home/H_STA/04/sta and the upper-host configuration tool at /home/H_STA/py_manage/moduleparasconfigtool. Use when a user asks to add, change, rename, remove, test, build, or package a firmware capability that is configured, packed, unpacked, displayed, or validated by the upper-host tool, especially changes to FileFooter, feature flags, province schemes, version-manager metadata, or their UI.
---

# SPLC dual-project feature synchronization

Read [references/binary-contract.md](references/binary-contract.md) before
changing FileFooter, packing/unpacking, or compatibility defaults. Read
[references/validation-packaging.md](references/validation-packaging.md) only
when validation, packer rebuilding, or Windows delivery is in scope.

## Keep command output out of model context

- Use `scripts/run_logged.py --log <evidence> --kind <build|pytest> --
  <command>` for verbose commands. It saves full output outside the repositories
  and returns timed compact JSON. Never use `tee`.
- Success output: command, exit code, elapsed time, counts, artifact metadata,
  and evidence path. Failure output: bounded first-cause context from
  `scripts/compact_log.py`; expand once if needed, never beyond 80 lines by
  default or 500 characters per line. Never load a complete log.
- Start repository inspection with branch, `status --short`, `diff --stat`,
  `diff --name-only`, and short `log --oneline`; then read only relevant hunks.
  Search for symbols/keys before opening files.
- Validate every province JSON in one machine pass but return only totals and
  failures. Inspect generated UI by symbol/diff hunk. Validate executables by
  exit code, size, hash, permissions, and round trip; never read/text-diff them.
- Batch independent read-only checks. Run focused checks first, generate once
  after sources stabilize, and reuse evidence while inputs stay unchanged.

## Execute from a named feature request

Treat the user's feature name and desired behavior as sufficient input when the
current repositories reveal the remaining details. Ask only when a choice would
change the protocol, default behavior, supported regions, or hardware target.

1. Inspect both repositories and local instructions with the bounded sequence
   above. Preserve unrelated user changes.
2. Trace firmware behavior, metadata, scheme default, editing, pack/unpack,
   display, and generated artifacts. Read only relevant definitions/call sites.
3. State any incompatible or incomplete requirement before expanding scope.
   Prefer backward-compatible defaults for old firmware and old schemes.
4. Use `wsl-safe-writing` for every mutation under `/home`. Use
   `test-driven-development` unless the user explicitly waives it.
5. Implement in the existing style. Keep binary layout, bit positions, field
   widths, structure packing, and line endings stable unless the requested
   behavior requires a versioned format change.
6. Synchronize affected province JSON and UI source/generated files; validate
   the complete JSON set programmatically.
7. Rebuild the pack/unpack executables whenever their Python sources or binary
   contract change, then copy the rebuilt Linux tools into the firmware
   version-manager directory. If a generated executable has a Git merge
   conflict, do not accept either binary as the final resolution: resolve the
   source merge first, regenerate both executables from the merged source, and
   validate the regenerated artifacts.
8. Run focused and relevant full upper-host tests, strict JSON/whitespace
   checks, and representative enabled/disabled firmware builds. Clean before
   every region change, including the final switch back; cross-region
   incremental objects are invalid evidence. If the user explicitly waives a
   test, record the exact waived scope and immediately remove it from the run;
   do not let a default TDD/full-test plan reintroduce it.
9. Rebuild and smoke-test Windows delivery when in scope.
10. Report changed behavior, compatibility decisions, test/build evidence,
    artifact paths, elapsed times, and uncommitted status. Do not paste logs
    already represented by an evidence path.

## Boundaries

- Do not flash hardware merely because a build succeeds. If the user requests
  board flashing or serial verification, invoke `splc-flash-loop` and follow
  its authorization rules.
- Do not silently import unrelated firmware features solely to make structures
  match. Add the smallest explicit compatibility representation and explain it.
- Do not commit, stage, reset, or discard work unless the user requests it.
- Do not treat generated Unity test images as proof that tests ran on a board.
