#!/usr/bin/env python3
"""Portable, standard-library entrypoint for the Darktide model replacement toolkit."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache"
CONFIG = ROOT / ".local" / "config.json"


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_config():
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inside(root, relative):
    relative = str(relative)
    portable = PurePosixPath(relative.replace('\\', '/'))
    if not relative or portable.is_absolute() or PureWindowsPath(relative).drive or '..' in portable.parts:
        raise ValueError(f'Path is not a safe relative resource path: {relative}')
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"Path escapes its owning directory: {relative}")
    return target


def unpack(archive, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        for member in source.infolist():
            inside(destination, member.filename)
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError("Archive contains a symbolic link")
        source.extractall(destination)


def download(item, destination):
    destination = Path(destination)
    expected = item["sha256"]
    if destination.exists() and sha256(destination) == expected:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    request = urllib.request.Request(item["url"], headers={"User-Agent": "Darktide-Model-Tools/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
        shutil.copyfileobj(response, output)
    if sha256(temporary) != expected:
        temporary.unlink()
        raise ValueError(f"SHA256 mismatch for {item['url']}; review the dependency lock before updating")
    temporary.replace(destination)
    return destination


def steam_libraries():
    roots = []
    if os.name == "nt":
        import winreg
        for hive, key, field in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
                                 (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")]:
            try:
                with winreg.OpenKey(hive, key) as handle:
                    roots.append(Path(winreg.QueryValueEx(handle, field)[0]))
            except OSError:
                pass
    roots.extend([Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Steam",
                  Path.home() / ".local/share/Steam"])
    result = []
    for root in roots:
        if root not in result and root.is_dir():
            result.append(root)
        manifest = root / "steamapps/libraryfolders.vdf"
        if manifest.is_file():
            for value in re.findall(r'"path"\s+"([^"]+)"', manifest.read_text(encoding="utf-8")):
                library = Path(value.replace("\\\\", "\\"))
                if library not in result:
                    result.append(library)
    return result


def discover_game():
    value = os.environ.get("DARKTIDE_GAME")
    if value:
        return Path(value)
    for library in steam_libraries():
        candidate = library / "steamapps/common/Warhammer 40,000 DARKTIDE"
        if (candidate / "bundle").is_dir():
            return candidate
    return None


def discover_blender():
    value = os.environ.get("BLENDER_EXE") or shutil.which("blender")
    if value:
        return Path(value)
    for library in steam_libraries():
        candidate = library / "steamapps/common/Blender/blender.exe"
        if candidate.is_file():
            return candidate
    base = Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Blender Foundation"
    if base.exists():
        candidates = sorted(base.glob("Blender */blender.exe"), reverse=True)
        if candidates:
            return candidates[0]
    return None


def executable(config, name):
    path = Path(config.get(name, "__missing__"))
    if not path.is_file():
        raise ValueError(f"{name} is not configured; run setup or pass its path during setup")
    return path


def run(command, **kwargs):
    print("Running:", " ".join(str(part) for part in command), flush=True)
    subprocess.run([str(part) for part in command], check=True, **kwargs)


def murmur64(text):
    data = text.encode("utf-8")
    multiplier, mask = 0xC6A4A7935BD1E995, (1 << 64) - 1
    value = (len(data) * multiplier) & mask
    end = len(data) // 8 * 8
    for offset in range(0, end, 8):
        word = int.from_bytes(data[offset:offset + 8], "little")
        word = word * multiplier & mask
        word ^= word >> 47
        word = word * multiplier & mask
        value = ((value ^ word) * multiplier) & mask
    tail = data[end:]
    if tail:
        value ^= int.from_bytes(tail, "little")
        value = value * multiplier & mask
    value ^= value >> 47
    value = value * multiplier & mask
    value ^= value >> 47
    return value


def setup(args):
    config = load_config()
    game = Path(args.game) if args.game else discover_game()
    blender = Path(args.blender) if args.blender else discover_blender()
    if game is None or not (game / "bundle").is_dir():
        raise ValueError("Game installation not found. Use setup --game PATH; extracted game files stay local.")
    if blender is None or not blender.is_file():
        raise ValueError("Blender not found. Use setup --blender PATH (tested baseline: Blender 5.2).")
    config.update(game=str(game.resolve()), blender=str(blender.resolve()))
    lock = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    for name in ("sdk", "limn", "mmr"):
        item = lock[name]
        archive = download(item, CACHE / "downloads" / (name + ".zip"))
        destination = CACHE / "dependencies" / name
        marker = destination / ".archive-sha256"
        if not marker.is_file() or marker.read_text().strip() != item["sha256"]:
            unpack(archive, destination)
            marker.write_text(item["sha256"], encoding="ascii")
        if name == "sdk":
            config["compiler"] = str(next(destination.rglob("DarktideGLBCompiler.exe")).resolve())
            addon = next(destination.rglob("darktide_assets_blender.zip"))
            unpack(addon, CACHE / "blender-addons")
            config["addon_parent"] = str((CACHE / "blender-addons").resolve())
        elif name == "limn":
            config["limn"] = str(next(destination.rglob("limn.exe")).resolve())
        else:
            config["mmr_source"] = str(destination.resolve())
    dll = game / "binaries/oo2core_9_win64.dll"
    if not dll.is_file():
        raise ValueError("The game-supplied Oodle DLL is missing from binaries; it is not redistributed here.")
    shutil.copy2(dll, Path(config["limn"]).parent / dll.name)
    run([config["compiler"], "--configure-oodle", game])
    config["extract"] = str((CACHE / "game-reference").resolve())
    save_json(CONFIG, config)
    if not args.skip_extract:
        extract_references(config)
    print(json.dumps(doctor_report(config), ensure_ascii=False, indent=2))


def extract_references(config):
    output = Path(config["extract"])
    output.mkdir(parents=True, exist_ok=True)
    resources = ["content/characters/player/human/third_person/base",
                 "content/characters/player/human/first_person/base"]
    selection = CACHE / "skeleton-resources.txt"
    selection.write_text("\n".join(f"@{murmur64(name):016x}={murmur64(name):016x}" for name in resources) + "\n", encoding="utf-8")
    log = CACHE / 'extract-skeletons.log'
    print(f'Extracting local skeletons; detailed log: {log}', flush=True)
    with log.open('w', encoding='utf-8') as stream:
        run([executable(config, "limn"), "--dump-raw", "-i", Path(config["game"]) / "bundle",
             "-o", output, "--dict", selection, "unit", "bones"], cwd=Path(config["limn"]).parent,
             stdout=stream, stderr=subprocess.STDOUT)
    for name in resources:
        for extension in ("unit", "bones"):
            if not (output / f"{murmur64(name):016x}.{extension}").is_file():
                raise ValueError(f"Extractor did not produce {name}.{extension}; a zero exit code is insufficient")


def doctor_report(config):
    game = Path(config.get("game", "__missing__"))
    mods = game / 'mods'
    api_files = sorted(mods.rglob('CustomAssets.mod')) if mods.is_dir() else []
    if not api_files and mods.is_dir():
        api_files = sorted(mods.rglob('CustomAssets.lua'))
    return {
        "python": sys.version.split()[0],
        "configured": bool(config),
        "tools": {key: Path(config.get(key, "__missing__")).is_file() for key in ("blender", "compiler", "limn")},
        "skeletons": {perspective: all((Path(config.get("extract", "__missing__")) /
            f"{murmur64('content/characters/player/human/' + perspective + '/base'):016x}.{ext}").is_file()
            for ext in ("unit", "bones")) for perspective in ("third_person", "first_person")},
        "game_mod_prerequisites": {
            "dml": (game / "binaries/mod_loader").is_file(),
            "dmf": (game / "mods/dmf/dmf.mod").is_file(),
            "custom_assets": bool(api_files),
            "patcher": (game / "tools/custom-assets-patcher.exe").is_file(),
        },
        'custom_assets_api_locations': [str(p.relative_to(game)) for p in api_files],
        'custom_assets_load_order_verified': False,
        "note": "DML, DMF and Custom Assets must be installed from their original publishers. See docs/tools.md.",
    }


def blender_job(config, mode, source, output, **extra):
    source, output = Path(source).resolve(), Path(output).resolve()
    if not source.is_file() or source.suffix.lower() != ".blend":
        raise ValueError("Supply an existing .blend file")
    output.mkdir(parents=True, exist_ok=True)
    before = sha256(source)
    job = dict(config, mode=mode, source=str(source), output=str(output), source_sha256=before, **extra)
    job_path = output / "job.local.json"
    save_json(job_path, job)
    run([executable(config, "blender"), "--background", "--factory-startup", "--disable-autoexec",
         source, "--python-exit-code", "1", "--python", ROOT / "tools/blender/worker.py", "--", job_path])
    if sha256(source) != before:
        raise ValueError("Source blend changed unexpectedly; stop before packaging")


def inspect_model(args):
    config = load_config()
    if args.blender:
        config["blender"] = args.blender
    blender_job(config, "inspect", args.source, args.output)


def build(args):
    config = load_config()
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    slug = profile.get("id", "")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,47}", slug):
        raise ValueError("Profile id must be 2-48 lowercase ASCII letters, digits or underscores, starting with a letter")
    if profile.get("kind") not in ("character", "weapon"):
        raise ValueError("Profile kind must be character or weapon")
    output = Path(args.output or ROOT / "work" / slug).resolve()
    if (output / "build-report.json").exists():
        raise ValueError("Build output already exists; choose a new candidate output directory")
    blender_job(config, "build", args.source, output, profile=profile)
    manifests = list(output.glob("compiled/*/build.json"))
    if not manifests:
        raise ValueError("No compiled build manifests were produced")
    report = [validate_manifest(path) for path in manifests]
    save_json(output / "resource-audit.json", report)
    print(f"Built isolated candidate at {output}. In-game validation has not been performed.")


def validate_manifest(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8-sig"))
    resources = {(r["key"]["type"], r["key"]["name"]): r for r in manifest["resources"]}
    if not resources or len(resources) != len(manifest['resources']):
        raise ValueError('Manifest must contain nonempty, unique resource identities')
    external = {(r.get("key", r)["type"], r.get("key", r)["name"]) for r in manifest.get("external_resources", [])}
    for root in manifest.get('roots', []):
        if (root['type'], root['name']) not in resources:
            raise ValueError('Manifest root is not in the local resource set')
    checked = set()
    import zlib
    for resource in resources.values():
        for entry in [resource["file"], *([resource["stream"]["file"]] if resource.get("stream") else [])]:
            artifact = inside(path.parent, entry["path"])
            raw = artifact.read_bytes()
            if "size" in entry and len(raw) != entry["size"]:
                raise ValueError(f"Artifact size mismatch: {artifact.name}")
            if "crc32" in entry and f"{zlib.crc32(raw):08x}" != str(entry["crc32"]).lower():
                raise ValueError(f"Artifact CRC mismatch: {artifact.name}")
            checked.add(str(artifact))
        for dependency in resource.get("dependencies", []):
            key = dependency["type"], dependency["name"]
            if key not in resources and key not in external:
                raise ValueError(f"Unresolved resource dependency: {key}")
    for artifact in manifest.get("artifacts", []):
        f = inside(path.parent, artifact["path"])
        if not f.is_file() or ("size" in artifact and f.stat().st_size != artifact["size"]):
            raise ValueError(f"Missing or inconsistent artifact: {artifact['path']}")
    return {"manifest": str(path), "resources": len(resources), "files": len(checked),
            "unit_material_binding_check": "compiler --validate plus toolkit native audit; see native-audit.json"}


def install_skill(args):
    source = ROOT / "skills/darktide-model-replacement"
    base = Path(args.destination) if args.destination else Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"
    target = base / source.name
    if target.exists():
        if not args.replace:
            raise ValueError(f"Skill already exists: {target}; use --replace to create a backup and update it")
        backup = base.parent / 'skill-backups' / (source.name + '.' + str(time.time_ns()))
        backup.parent.mkdir(parents=True, exist_ok=True)
        target.rename(backup)
        print(f'Previous skill backed up outside discovery directory: {backup}')
    shutil.copytree(source, target)
    (target / "repository-location.txt").write_text(str(ROOT) + "\n", encoding="utf-8")
    print(f"Installed skill: {target}")


def materialize(args):
    config = load_config()
    destination = Path(args.output).resolve()
    if destination.exists():
        raise ValueError("Choose an empty materialization directory")
    replacements = {
        "<CHARACTER_WORKSPACE>": str(destination / "AnimeModelReplacement"),
        "<WEAPON_WORKSPACE>": str(destination / "WeaponModelReplacement"),
        "<DARKTIDE_GAME>": config.get("game", "__configure_game__"),
        "<BLENDER_EXE>": config.get("blender", "__configure_blender__"),
        "<SOURCE_ROOT>": str(destination / "sources"),
        "<SCREENSHOT_ROOT>": str(destination / "screenshots"),
        "<WINDOWS_FONTS>": str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"),
        "<LUA_EXE>": shutil.which("lua") or "lua",
        "<LUAC_EXE>": shutil.which("luac") or "luac",
    }
    for kind, folder in [("character", "AnimeModelReplacement/tools/model-work"), ("weapon", "WeaponModelReplacement/tools")]:
        for source in (ROOT / "toolbox" / kind).glob("*"):
            if not source.is_file():
                continue
            text = source.read_text(encoding="utf-8")
            for token, value in replacements.items():
                text = text.replace(token, value.replace("\\", "/"))
            out = destination / folder / source.name
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
    print(f"Materialized source adapters at {destination}; regenerate source-profile reports and supply licensed templates before running legacy builds.")


def package(args):
    from package_mod import package_candidate
    print(package_candidate(Path(args.candidate), Path(args.runtime), Path(args.output), ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("setup", help="Download verified upstream tools and extract local native skeletons")
    command.add_argument("--game")
    command.add_argument("--blender")
    command.add_argument("--skip-extract", action="store_true")
    command.set_defaults(func=setup)
    command = commands.add_parser("doctor", help="Report tools, references and game-mod prerequisites")
    command.set_defaults(func=lambda _: print(json.dumps(doctor_report(load_config()), ensure_ascii=False, indent=2)))
    command = commands.add_parser("inspect", help="Inspect a source .blend without saving it")
    command.add_argument("source")
    command.add_argument("--output", default=str(ROOT / "work/inspection"))
    command.add_argument("--blender")
    command.set_defaults(func=inspect_model)
    command = commands.add_parser("build", help="Compile a reviewed character or weapon profile")
    command.add_argument("source")
    command.add_argument("--profile", required=True)
    command.add_argument("--output")
    command.set_defaults(func=build)
    command = commands.add_parser("validate", help="Check a Custom Assets build.json and its resource closure")
    command.add_argument("manifest")
    command.set_defaults(func=lambda args: print(json.dumps(validate_manifest(args.manifest), indent=2)))
    command = commands.add_parser("install-skill", help="Install the skill and remember this repository location")
    command.add_argument("--destination")
    command.add_argument("--replace", action="store_true")
    command.set_defaults(func=install_skill)
    command = commands.add_parser("materialize-toolbox", help="Create configurable working copies of historical source adapters")
    command.add_argument("--output", required=True)
    command.set_defaults(func=materialize)
    command = commands.add_parser("package", help="Combine compiled candidate and reviewed runtime into a distributable mod")
    command.add_argument("candidate")
    command.add_argument("--runtime", required=True)
    command.add_argument("--output", required=True)
    command.set_defaults(func=package)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
