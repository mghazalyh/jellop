# RPCS3 development target

Hardware defaults to BUILD_FOR_RPCS3=0; build the emulator with a fresh checkout
and make BUILD_FOR_RPCS3=1 pkg. Never reuse object files across target changes.
Both packages use JELP30001; use separate emulator profiles.

Source reviewed: RPCS3/rpcs3 commit 0ca5eb0efe50ec4e8aa07892ab86d57842246eb4.
- rpcs3/rpcs3.cpp: headless CLI supports firmware and package installation;
  --no-gui retains graphical rendering and accepts --config.
- rpcs3/headless_application.cpp: headless boot requires the null renderer.
  It cannot prove picture output.
- rpcs3/Emu/Cell/Modules/cellVdec.cpp: H.264 uses FFmpeg and planar YUV420.
  Preserve slot bounds checks, emulator CPU compositing and RSX fences.
- rpcs3/Emu/Cell/Modules/cellSaveData.cpp: saves belong to the active user.
- rpcs3/Emu/system_config.h and vfs_config.h: network defaults to disabled,
  bind address is configurable, dev_hdd0 defaults to EmulatorDir.

Manual testing: install official firmware and the emulator package using
RPCS3's File menu. Enable Network > Internet enabled: Connected, use a reachable
bridge URL, and choose Vulkan or OpenGL, not Null. If compositing fails, compare
OpenGL with Write Color Buffers and Read Color Buffers enabled. L3 starts Surf
in Live TV and pauses/resumes Surf during playback.

The optional native fixture driver requires an emulator build, a specific
scratch marker and the exact local fixture server/token. It calls the ordinary
catalogue and playback paths. It does not test controller input or prove
physical hardware compatibility.

## Isolated CI smoke

The [separate workflow](../.github/workflows/rpcs3.yml) downloads a pinned RPCS3 binary and Sony firmware onto an ephemeral runner. Firmware is not included in artifacts. Synthetic HLS uses two channels and 15-second Surf dwell. A pass requires a two-channel catalogue, actual native frame progress for both channels, an automatic transition, and increasing frame counters after the transition. The GUI run uses Mesa software OpenGL under Xvfb; it is not a physical performance benchmark. The workflow runs on pushes and manual dispatch only.

Firmware download provenance: Sony's official 4.93 support link uses HTTP; the CI verifies the exact 206,197,916-byte firmware against the SHA-256 in https://github.com/ScoopInstaller/Games/blob/master/bucket/ps3-system-software.json before installation. No TLS verification bypass is used. The Linux RPCS3 log is collected from XDG_CACHE_HOME/rpcs3, not the config directory.

CI bootstrap notes: the pinned Linux binary needs libOpenGL.so.0. Its headless installer can hit a teardown assertion after successful installation; the workflow accepts that exact assertion only after explicit firmware/package success logs and installed-file validation. The graphical software-rendered smoke test disables the unused Qt Music Handler and camera integration because the first run froze on the host during Qt music initialization, before native guest breadcrumbs. Fatal RPCS3 freeze messages now fail the test immediately. These are CI-only configuration choices, not a change to console code or manual emulator audio output.

RPCS3 serializes its enum value `Null` as a quoted YAML string. The second boot log showed that unquoted `Null` retained the defaults Cubeb and Qt even though the override file loaded. The smoke harness now quotes these enum values and checks the effective boot configuration before accepting a playback result. Failure screenshots are captured before terminating the emulator process.

Fixture driver setup uses the installed USRDIR rather than volatile guest scratch storage. The normal Live TV tab entry and render-thread catalogue pump run with explicit spine level selection; invalid or missing test marker fails the runner promptly. The boot and playback watchdogs are separate to allow cold PPU/SPU compilation. Public fixture retrieval matches the successful Jealouswin Node HTTPS deployment verifier, with bounded responses and existing SHA-256 validation.

Library discovery now uses the shared bounded JSON reader instead of requiring a compact `Items` key; regression fixtures cover whitespace, nested keys, escapes, and malformed rows. The fixture tab entry uses `SPINE_L2` (category), not a numeric level.

The 35045a14 two-channel graphical smoke passed (first channel frame 448 before switch; second channel frame 521 after switch). The expanded acceptance now downloads the verified public Jealouswin fixture, exposes two eligible channels plus one banned and one on hiatus, and requires four automatic transitions, correct cycle rollover, five decoded sessions, current programme titles, monotonic frame/decoded-time evidence and zero recorded stalls. It records the actual free guest memory rather than claiming measured physical hardware performance. The test uses a null host audio backend and does not validate audible audio or human controller input.
