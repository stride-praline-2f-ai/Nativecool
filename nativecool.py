#!/usr/bin/env python3
"""Build one of Nativecool's game profiles using a local backend checkout."""

import argparse
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile


FRAMEGEN_REVISION = "07d8ba52b671053dd67286ba3586b4ced4100203"
FRAMEGEN_PATCH = Path(__file__).resolve().parent / "patches/shared-frame-generation.patch"


# Name, title ID, package version, backend, Xcode release
PROFILES = {
    "ocarina": (
        "Ocarina of Time (Switch 2 Edition)", "0400486024DEC000",
        "v131072", "NX18", "27.3",
    ),
    "overcooked": (
        "Overcooked! All You Can Eat", "0100F28011892000",
        "v786432", "nxnative", "27.2",
    ),
    "dungeons": (
        "Minecraft Dungeons II (Switch)", "0100A7C01B792000",
        "v131072", "nxnative", "27.2",
    ),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=PROFILES)
    parser.add_argument("input", type=Path, help="local game file or dump folder")
    parser.add_argument("--backend", required=True, type=Path,
                        help="path to the game's backend checkout")
    parser.add_argument("--screen-shape-engine", action="store_true",
                        help="use richservo's experimental totk-screen-shape checkout")
    parser.add_argument("--duo", action="store_true",
                        help="package the shared iPhone Duo settings")
    parser.add_argument("--picture", choices=("fit", "fill", "match"),
                        help="Duo picture mode (fill crops, match needs a game-specific viewport)")
    parser.add_argument("--frame-generation", choices=("30", "60"),
                        help="experimental MetalFX interpolation at the selected real FPS")
    parser.add_argument("--keys", type=Path, help="local keys for encrypted packages")
    parser.add_argument("--platform", choices=("ios", "mac-app"), default="ios")
    parser.add_argument("--output-dir", type=Path, default=Path("build"))
    parser.add_argument("--bundle-romfs", action="store_true",
                        help="include game data in the IPA")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    name, title_id, version, backend_name, xcode = PROFILES[args.game]

    backend = args.backend.expanduser().resolve()
    game = args.input.expanduser().resolve()
    keys = args.keys.expanduser().resolve() if args.keys else None
    packer = backend / "scripts" / "build_ipa_from_nsp.py"
    profile = backend / "dm" / "games" / title_id / "game.tsv"
    if not packer.is_file() or not profile.is_file():
        parser.error(f"Use a {backend_name} checkout containing profile {title_id}.")
    if not (game.is_file() or game.is_dir()):
        parser.error("The game input must be an existing file or directory.")
    if keys and not keys.is_file():
        parser.error("The supplied keys path must be an existing file.")
    if args.bundle_romfs and args.platform != "ios":
        parser.error("--bundle-romfs applies only to IPA builds.")
    if args.picture and not args.duo:
        parser.error("--picture requires --duo.")
    if args.duo and args.platform != "ios":
        parser.error("--duo applies only to IPA builds.")
    if args.screen_shape_engine:
        branch_notes = backend / "HOOKLINK.md"
        if not branch_notes.is_file() or "DM_FRAME_MODE" not in branch_notes.read_text():
            parser.error("--screen-shape-engine requires the richservo checkout with HookLink support.")
        backend_name, xcode = "richservo screen-shape", "27.2"
    if args.frame_generation:
        if not (args.duo and args.screen_shape_engine):
            parser.error("--frame-generation requires --duo and --screen-shape-engine.")
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=backend, capture_output=True, text=True,
        )
        if revision.returncode or revision.stdout.strip() != FRAMEGEN_REVISION:
            parser.error(f"Frame generation requires richservo's revision {FRAMEGEN_REVISION}.")

    settings = {}
    if args.duo:
        settings = {
            "DM_OPMODE": "0",
            "DM_PRESENT_UPSCALE": "metalfx",
            "DM_PSO_PREBUILD": "1",
            "DM_SHOW_FPS": "1",
            "DM_PICTURE_FIT": "fill" if args.picture == "fill" else "fit",
        }
        if args.picture == "match":
            if args.game == "ocarina" and args.screen_shape_engine:
                settings.update(DM_WIDE_VIEW="1", DM_WIDE_HUD="1")
            else:
                settings["DM_SCREEN_ASPECT"] = "auto"
                print("Match Screen requires title-specific viewport support. Check geometry and HUD on-device.",
                      flush=True)
        if args.frame_generation:
            settings["DM_NATIVECOOL_FRAMEGEN_FPS"] = args.frame_generation

    output_dir = args.output_dir.expanduser().resolve() / args.game / args.platform
    if args.screen_shape_engine:
        output_dir /= "screen-shape"
    if args.duo:
        output_dir /= "duo-" + (args.picture or "fit")
    if args.frame_generation:
        output_dir /= "framegen-" + args.frame_generation
    extension = ".ipa" if args.platform == "ios" else ".app"
    artifact = output_dir / (args.game + extension)
    command = [
        sys.executable, "-I", str(packer), str(game),
        "--title-id", title_id, "--package", version, "--platform", args.platform,
        "--work-dir", str(output_dir / "work"), "-o", str(artifact),
    ]
    if args.platform == "ios":
        command += ["--romfs", "bundle" if args.bundle_romfs else "separate"]
    settings_file = output_dir / "duo.env"
    settings_text = "".join(f"{key}={value}\n" for key, value in settings.items())
    if settings:
        command += ["--gpu", "g19p", "--env-file", str(settings_file)]

    print(f"{name} · {version} · {backend_name} · Xcode {xcode}", flush=True)
    print(f"Output: {artifact}", flush=True)
    if args.dry_run:
        if args.frame_generation:
            print(f"Apply {FRAMEGEN_PATCH.name} in a temporary backend worktree.")
        redacted = command + (["-k", "<local keys file>"] if keys else [])
        print(shlex.join(redacted))
        if settings_text:
            print(settings_text, end="")
        return 0
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("Build on an Apple silicon Mac. --dry-run is portable.")
    if sys.version_info < (3, 12):
        parser.error("Use Python 3.12 or later for the packer.")

    if keys:
        command += ["-k", str(keys)]
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        if settings_text:
            settings_file.write_text(settings_text, encoding="utf-8")
        if args.frame_generation:
            with tempfile.TemporaryDirectory(prefix="nativecool-") as directory:
                patched = Path(directory) / "engine"
                subprocess.run(["git", "worktree", "add", "--detach", str(patched),
                                FRAMEGEN_REVISION], cwd=backend, check=True)
                try:
                    subprocess.run(["git", "apply", str(FRAMEGEN_PATCH)],
                                   cwd=patched, check=True)
                    command[2] = str(patched / packer.relative_to(backend))
                    result = subprocess.run(command, cwd=patched, check=False)
                finally:
                    subprocess.run(["git", "worktree", "remove", "--force", str(patched)],
                                   cwd=backend, check=True)
        else:
            result = subprocess.run(command, cwd=backend, check=False)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Preparing the patched engine failed (exit {error.returncode}).\n")
    except OSError as error:
        parser.exit(1, f"Build could not start: {error}\n")
    if result.returncode:
        return result.returncode if result.returncode > 0 else 128 - result.returncode
    if not artifact.exists():
        parser.exit(1, f"The packer exited without producing {artifact}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
