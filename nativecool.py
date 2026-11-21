#!/usr/bin/env python3
"""Build the Nativecool engine and package a supported title for iPhone Duo or Mac."""

import argparse
import fcntl
import hashlib
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
ENGINE_URL = "https://github.com/richservo/nxnative.git"
ENGINE_REVISION = "07d8ba52b671053dd67286ba3586b4ced4100203"
ENGINE_PATCHES = (
    ROOT / "patches/nx18-queue-and-warmup.patch",
    ROOT / "patches/presentation-counter.patch",
    ROOT / "patches/shared-frame-generation.patch",
)

# Name, title ID, package version
PROFILES = {
    "ocarina": ("Ocarina of Time (Switch 2 Edition)", "0400486024DEC000", "v131072"),
    "overcooked": ("Overcooked! All You Can Eat", "0100F28011892000", "v786432"),
    "dungeons": ("Minecraft Dungeons II (Switch)", "0100A7C01B792000", "v131072"),
}


def engine_version():
    digest = hashlib.sha256(ENGINE_REVISION.encode())
    for patch in ENGINE_PATCHES:
        digest.update(hashlib.sha256(patch.read_bytes()).digest())
    return digest.hexdigest()[:16]


def prepare_engine(engine, source):
    """Materialize a pinned, patched engine in a temporary sibling directory."""
    if engine.is_dir():
        return
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=engine.parent) as directory:
        staged = Path(directory) / "engine"
        subprocess.run(["git", "init", "--quiet", str(staged)], check=True)
        subprocess.run(
            ["git", "fetch", "--depth", "1", str(source), ENGINE_REVISION],
            cwd=staged, check=True,
        )
        subprocess.run(
            ["git", "checkout", "--quiet", "--detach", ENGINE_REVISION],
            cwd=staged, check=True,
        )
        subprocess.run(
            ["git", "apply", "--index", "--whitespace=error", *map(str, ENGINE_PATCHES)],
            cwd=staged, check=True,
        )
        staged.rename(engine)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", choices=PROFILES)
    parser.add_argument("input", type=Path, help="local game file or dump folder")
    parser.add_argument("--source", "--backend", type=Path,
                        help="optional local checkout containing the pinned engine revision")
    parser.add_argument("--engine-cache", type=Path, default=ROOT / ".local")
    parser.add_argument("--screen-shape-engine", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--duo", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--picture", choices=("fit", "fill", "match"),
                        help="fit without cropping, fill by cropping, or match for Ocarina")
    parser.add_argument("--frame-generation", choices=("30", "60"),
                        help="experimental MetalFX interpolation at the selected real FPS")
    parser.add_argument("--keys", type=Path, help="local keys for encrypted packages")
    parser.add_argument("--platform", choices=("ios", "mac-app"), default="ios")
    parser.add_argument("--output-dir", type=Path, default=Path("build"))
    parser.add_argument("--bundle-romfs", action="store_true",
                        help="include game data in the IPA")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    name, title_id, version = PROFILES[args.game]

    game = args.input.expanduser().resolve()
    keys = args.keys.expanduser().resolve() if args.keys else None
    source = args.source.expanduser().resolve() if args.source else ENGINE_URL
    if args.source and not source.is_dir():
        parser.error("--source must point to an existing local Git checkout.")
    if not (game.is_file() or game.is_dir()):
        parser.error("The game input must be an existing file or directory.")
    if keys and not keys.is_file():
        parser.error("The supplied keys path must be an existing file.")
    ios = args.platform == "ios"
    if not ios and (args.duo or args.picture or args.frame_generation or args.bundle_romfs):
        parser.error("The Duo picture, frame generation and RomFS options apply to IPA builds.")
    if args.picture == "match" and args.game != "ocarina":
        parser.error("This title needs a camera and HUD patch for Match Screen. Choose fit or fill.")

    revision = engine_version()
    cache = args.engine_cache.expanduser().resolve()
    engine = cache / f"engine-{revision}"
    packer = engine / "scripts/build_ipa_from_nsp.py"
    output = args.output_dir.expanduser().resolve() / args.game / args.platform / revision
    settings = {}
    if ios:
        picture = args.picture or "fit"
        output /= f"duo-{picture}"
        settings = {
            "DM_OPMODE": "0",
            "DM_PSO_MTL4": "1",
            "DM_PSO_PREBUILD": "1",
            "DM_PRESENT_UPSCALE": "metalfx",
            "DM_SHOW_FPS": "1",
            "DM_PICTURE_FIT": "fill" if picture == "fill" else "fit",
        }
        if picture == "match":
            settings.update(DM_WIDE_VIEW="1", DM_WIDE_HUD="1")
        if args.frame_generation:
            output /= f"framegen-{args.frame_generation}"
            settings["DM_NATIVECOOL_FRAMEGEN_FPS"] = args.frame_generation
        else:
            settings.update(DM_FRAME_MODE="0", DM_FRAMEGEN="0")

    extension = ".ipa" if ios else ".app"
    artifact = output / (args.game + extension)
    command = [
        sys.executable, "-I", str(packer), str(game),
        "--title-id", title_id, "--package", version, "--platform", args.platform,
        "--work-dir", str(output / "work"), "-o", str(artifact),
    ]
    settings_file = output / "duo.env"
    settings_text = "".join(f"{key}={value}\n" for key, value in settings.items())
    if ios:
        command += ["--romfs", "bundle" if args.bundle_romfs else "separate",
                    "--gpu", "g19p", "--env-file", str(settings_file)]

    print(f"{name} · {version} · Nativecool engine {revision} · Xcode 27.2", flush=True)
    print(f"Output: {artifact}", flush=True)
    if args.dry_run:
        print(f"Engine base: {ENGINE_REVISION}")
        print(shlex.join(command + (["-k", "<local keys file>"] if keys else [])))
        print(settings_text, end="")
        return 0
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("Build on an Apple silicon Mac. --dry-run is portable.")
    if sys.version_info < (3, 12):
        parser.error("Use Python 3.12 or later for the packer.")

    if keys:
        command += ["-k", str(keys)]
    try:
        cache.mkdir(parents=True, exist_ok=True)
        # The packer generates files in the engine source tree as well as the work folder.
        with (cache / f"{engine.name}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            prepare_engine(engine, source)
            output.mkdir(parents=True, exist_ok=True)
            if settings:
                settings_file.write_text(settings_text, encoding="utf-8")
            result = subprocess.run(command, cwd=engine, check=False)
    except subprocess.CalledProcessError as error:
        parser.exit(1, f"Preparing the unified engine failed (exit {error.returncode}).\n")
    except OSError as error:
        parser.exit(1, f"Build could not start: {error}\n")
    if result.returncode:
        return result.returncode if result.returncode > 0 else 128 - result.returncode
    if not artifact.exists():
        parser.exit(1, f"The packer exited without producing {artifact}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
