# Nativecool

Nativecool builds all three titles with one patched nxnative engine. It fetches a pinned source revision, applies the patches in this repo, and reuses the resulting checkout for every title. The game files, keys, caches and unsigned IPAs stay on your build machine.

## Build an IPA

Use an Apple silicon Mac, Python 3.12 or newer, and full Xcode 27.2 with the iOS platform and Metal toolchain. Use the base engine’s setup instructions for the remaining dependencies. [Pinned engine prerequisites](https://github.com/richservo/nxnative/blob/07d8ba52b671053dd67286ba3586b4ced4100203/README.md#requirements)

```sh
python3 nativecool.py ocarina ~/Games/Ocarina.nup --picture match
python3 nativecool.py overcooked ~/Games/Overcooked --keys ~/Private/prod.keys
python3 nativecool.py dungeons ~/Games/DungeonsII --keys ~/Private/prod.keys
```

Use your local game data with the corresponding update. Ocarina uses Switch 2 update `v131072`. Overcooked uses Switch update 1.0.12 (`v786432`). Dungeons II uses the original Switch edition with update 1.1.3.0 (`v131072`).

The first build fetches the engine into `.local/`. Pass `--source /path/to/nxnative` to seed it from a local checkout containing commit `07d8ba52b671053dd67286ba3586b4ced4100203`. Pass `--engine-cache /path/to/cache` to put the engine on another volume. Builds under `build/` have separate output and intermediate files for each game, engine revision and presentation mode. The packer prints how to transfer the separate game image after installing the IPA. `--bundle-romfs` puts that image inside the IPA. Add `--platform mac-app` for a Mac comparison, or `--dry-run` to preview the command without fetching or building.

## Duo display and performance

The default IPA uses handheld mode, an A20 Pro pipeline archive (`g19p`), Metal 4 pipeline preparation, MetalFX upscaling and a presentation FPS counter. The display queue incorporates NX18’s standing-frame trim. After a sustained backlog it takes the newest queued frame once, then returns to FIFO. `DM_PRESENT_TRIM=0` in the app’s `Documents/env.txt` disables the trim for comparison.

- **Fit** preserves the full picture. **Fill** covers the screen without stretching by cropping; HUD elements near the edges may be clipped.
- **Match** uses the fork’s Ocarina-specific camera, HUD and movie handling. It asks for a viewport shaped to the app window and keeps the HUD at 16:9. The equivalent world projection and HUD work remains open for Overcooked and Dungeons II.
- **Frame generation** is opt-in for all three games. Add `--frame-generation 30` or `--frame-generation 60`. These request a real frame-rate target and enable the shared MetalFX interpolator without selecting Ocarina’s fixed simulation step. The 60 FPS option needs a 120 Hz display link to interpolate a frame between each pair. The engine can skip interpolation when frames arrive late.

The iOS FPS counter reports actual game frames shown and generated frames shown separately. To compare, build the same title with and without frame generation, then repeat the same route with a cold shader cache and a warm cache. For Ocarina, compare Kokiri Forest and Hyrule Field on both Duo screens. For Overcooked, check the opening kitchen with two controllers and all HUD elements in view. For Dungeons II, start offline and track memory and frame pacing through Escape from Squid Coast.

## Code origins

- **richservo nxnative** supplies the base engine, game profiles and per-title screen-shape hooks. The Tears of the Kingdom report shows the target for the unfolded Duo, with more world visible and 16:9 overlays. [Pinned fork](https://github.com/richservo/nxnative/tree/07d8ba52b671053dd67286ba3586b4ced4100203) · [Duo report](https://www.reddit.com/r/NativePortsOniOS/comments/1y1gpk8/tears_of_the_kingdom_on_iphone_duo_full_screen_no/)
- **HookLink** supplies the frame-generation runtime, Ocarina wide-view handling, and pipeline and memory changes carried by the fork. Nativecool adds a shared frame-generation mode in `dm/host/frame_mode.h`. [HookLink](https://github.com/dsi-hub/HookLink) · [Fork notes](https://github.com/richservo/nxnative/blob/07d8ba52b671053dd67286ba3586b4ced4100203/HOOKLINK.md)
- **NX18** supplies the standing-frame trim algorithm and 19 additional Ocarina render pipeline warmup rows. Its ten compute rows from that change already exist in the base manifest. Nativecool keeps the base engine’s Xcode 27.2 shader toolchain. [Queue trim](https://github.com/kencalx/NX18/commit/ce221c009ad98edce421a4b1815826dc6a7d2287) · [Ocarina warmup rows](https://github.com/kencalx/NX18/commit/ec0b7237accb6ac67dc297d85203d5cc67a42647)
- **The Ocarina Mac review** informed the separate presented-frame counters and the cold/warm comparison. Its frame rates and latency were measured on an M1 Pro. [Mac report](https://www.reddit.com/r/macgaming/comments/1xv8u9x/honest_review_ocarina_of_time_remake_performance/)

Source assembly and host-side checks have run on Linux. Xcode compilation, IPA installation, all three games’ frame timing and fullscreen on the Duo still need verification.
