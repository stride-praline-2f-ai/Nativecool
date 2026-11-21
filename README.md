# Nativecool

Nativecool builds local iPhone IPAs and Apple silicon Mac apps from the game files you supply. It selects a known title ID, game update and upstream profile, then delegates compilation to a local checkout. The intended phone target is Apple's [A20 Pro iPhone Duo](https://www.apple.com/iphone-duo/specs/).

## Build on your Mac

Use an Apple silicon Mac with Python 3.12+ and the full Xcode installation, iOS platform and Metal toolchain required by the selected backend. Follow each backend's setup for Homebrew and Python dependencies. You can select Xcode per invocation with `DEVELOPER_DIR` if both releases are installed.

| Game | Backend and tested game input | Phone status |
| --- | --- | --- |
| Ocarina of Time (Switch 2 Edition) | [NX18](https://github.com/kencalx/NX18/blob/main/docs/building.md), Xcode 27.3, update `v131072` in a NUP or compatible dump | NX18 reports iPhone 18 Pro Max gameplay and requires iOS 27.3+. HookLink credits an independent Duo engine test. This wrapper has no Duo run yet. |
| Overcooked! All You Can Eat | [Upstream nxnative](https://github.com/seedds/nxnative), Xcode 27.2, Switch update 1.0.12 (`v786432`) | Upstream played the opening kitchen at 60 fps on Mac. Controller pairing and local co-op on iPhone still need testing. |
| Minecraft Dungeons II | [Upstream nxnative](https://github.com/seedds/nxnative), Xcode 27.2, original Switch update 1.1.3.0 (`v131072`) | Upstream tested early offline gameplay on Mac, including the smaller address layout intended for iPhone. Use a checkout with that 5 GB layout. First boot and sustained play on Duo are open. |

Keep your backend checkouts, game files and keys outside the repo. Each input folder should contain the corresponding game and update. Pass `--keys` for encrypted Switch packages. Use the same backend revision when comparing runs.

```sh
python3 nativecool.py ocarina ~/Games/Ocarina.nup --backend ~/src/NX18
python3 nativecool.py overcooked ~/Games/Overcooked --backend ~/src/nxnative --keys ~/Private/prod.keys
python3 nativecool.py dungeons ~/Games/DungeonsII --backend ~/src/nxnative --keys ~/Private/prod.keys
```

Add `--dry-run` to check the paths and generated command without running the packer. Add `--platform mac-app` for a Mac gameplay baseline. Outputs and reusable work files live under `build/<game>/<platform>/` by default. The iOS build writes an unsigned IPA and separate game data. Follow the backend's signing, install and game-data transfer instructions for its output. The packer's output supplies the transfer details. Use `--bundle-romfs` if you need the game data inside the IPA and your installer can handle its size.

## Shared iPhone Duo features

Add `--duo` to any of the three commands above. This packages handheld mode, MetalFX present upscaling, pipeline preparation, an FPS counter and aspect-preserving Fit. It requests the A20 GPU pipeline archive (`g19p`). Shader prewarm coverage comes from the selected game's upstream profile. The bundled settings are fixed for that build. Launch without `--duo` for an upstream-default comparison.

- `--duo --picture fill` fills the display without stretching by cropping the picture. Check HUD and multiplayer margins before using it.
- `--duo --picture match` requests the backend's display-matched viewport. The option only changes the world framing when the game has the corresponding viewport support. Fit remains the presentation mode. On Ocarina with the screen-shape engine this selects the title’s Wide View with a centered 16:9 HUD and movies. The Duo-shaped Ocarina mode still needs a device test. True fullscreen with a separate 16:9 HUD is verified in the linked Tears of the Kingdom report. Overcooked and Dungeons still need their own world projection and HUD composition changes.
- `--screen-shape-engine` selects the experimental richservo engine with HookLink-derived runtime code. The branch contains profiles for all three target games, including the smaller Dungeons memory layout. Frame generation, real-time frame stepping, pipeline handling and viewport behavior still depend on the title and the engine's runtime gates. Zelda-specific rendering and timing changes require equivalent game-specific work for Overcooked and Dungeons. Use the original build route as a comparison.

~~~sh
git clone --branch totk-screen-shape https://github.com/richservo/nxnative.git ~/src/nxnative-screen-shape
python3 nativecool.py ocarina ~/Games/Ocarina.nup --backend ~/src/nxnative-screen-shape --screen-shape-engine --duo --picture match --dry-run
python3 nativecool.py overcooked ~/Games/Overcooked --backend ~/src/nxnative --keys ~/Private/prod.keys --duo
python3 nativecool.py dungeons ~/Games/DungeonsII --backend ~/src/nxnative --keys ~/Private/prod.keys --duo
~~~

Use Xcode 27.2 for the screen-shape checkout. Remove `--dry-run` to build. Preset and experimental builds have their own output and work directories, so you can compare them against upstream defaults.

### MetalFX frame generation

For any of the three games, add `--duo --screen-shape-engine --frame-generation 30` or `--frame-generation 60`. Nativecool compiles a small [host patch](patches/shared-frame-generation.patch) that selects the branch's shared MetalFX presentation path and keeps the game's simulation-step, hold and payback settings. The 30 FPS option targets a 60 Hz presentation and the 60 FPS option needs a 120 Hz display-link mode to interpolate a frame between each pair. The engine can skip interpolation when it falls behind. The requested timing, input latency and HUD motion still need to be measured on each game.

The patch targets richservo revision `07d8ba52b671053dd67286ba3586b4ced4100203`. Check out that commit in the screen-shape clone. The packer builds from a temporary worktree and leaves your checkout alone.

~~~sh
git -C ~/src/nxnative-screen-shape checkout --detach 07d8ba52b671053dd67286ba3586b4ced4100203
python3 nativecool.py ocarina ~/Games/Ocarina.nup --backend ~/src/nxnative-screen-shape --screen-shape-engine --duo --picture match --frame-generation 30
~~~

## What the five references tell us

- **HookLink** is the Zelda comparison build. Its documentation covers separate game-data transfer, startup pipeline preparation, lower-memory rendering and keeping game speed correct when frames take longer. Test an equivalent route and save on the same phone when comparing it with NX18. [HookLink](https://github.com/dsi-hub/HookLink)
- **NX18** has an A20-focused Metal 4 path, prebuilt pipelines, display queue tuning and a Match Screen option for supported games. Its device testing is on iPhone 18 Pro Max and it targets a different Metal compiler from upstream nxnative. Keep the backend toolchains and caches distinct. [NX18](https://github.com/kencalx/NX18)
- **The screen-shape branch** is a working reference for per-game display adjustments. Its branch documentation also describes keeping Zelda HUD and movie layers centered at 16:9. Start with Fit for all three games. Enable a display-matched 3D viewport only after checking HUD, menus, movie framing and touch alignment on each screen. [richservo branch](https://github.com/richservo/nxnative/tree/totk-screen-shape) · [Branch notes](https://github.com/richservo/nxnative/blob/totk-screen-shape/HOOKLINK.md)
- **The Duo Tears of the Kingdom post** shows the target presentation. Its author reports a taller scene at 60 fps with 16:9 overlays and links the branch above. Treat that as a result for Tears of the Kingdom and test the other titles separately. [Duo report](https://www.reddit.com/r/NativePortsOniOS/comments/1y1gpk8/tears_of_the_kingdom_on_iphone_duo_full_screen_no/)
- **The Mac Ocarina review** reports about 59 displayed fps from 30 rendered fps with frame generation and about 95 ms of input latency on an M1 Pro. It also reports first-area shader stutters. Record actual and displayed frame rates separately and measure cold and warm runs. [Mac performance report](https://www.reddit.com/r/macgaming/comments/1xv8u9x/honest_review_ocarina_of_time_remake_performance/)

## Duo validation

1. **Ocarina**. From a fresh save, play through Kokiri Forest and into Hyrule Field. Compare a real 30 fps baseline with 60 fps and with frame generation where available. Verify game speed, fog, cutscenes and save reload. Use the same route on both Duo displays.
2. **Overcooked**. Start the opening kitchen offline in Fit mode. Finish a level with one controller, then with two controllers. Background and resume, then reopen and check the save.
3. **Dungeons**. Start offline, reach Escape from Squid Coast, then move and fight through the level. Record peak memory, loading stalls and any graphics faults. Retest after a warm launch before trying a higher frame-rate mode.

For each run, record the game update, backend commit, iOS version, screen, resolution and any frame generation. Keep a first-launch measurement and a warm 20-minute run with frame times, thermal state and crashes. Verify the picture remains correctly proportioned after changing displays.

[Overcooked upstream profile](https://github.com/seedds/nxnative/tree/main/dm/games/0100F28011892000) · [Dungeons upstream profile](https://github.com/seedds/nxnative/tree/main/dm/games/0100A7C01B792000) · [NX18 Ocarina profile](https://github.com/kencalx/NX18/tree/main/dm/games/0400486024DEC000)
