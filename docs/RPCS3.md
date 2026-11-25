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
