# Darktide Character & Weapon Model Replacement Toolkit

[中文](README.md) · [Quick start](docs/quickstart.md) · [Tools](docs/tools.md)

An installable AI skill, practical knowledge base, portable build tools and Lua runtime templates for adapting your own Blender models to Warhammer 40,000: Darktide. Includes 263 historical adaptation scripts and 32 runtime reference files. Case notes are mostly in English; getting-started guides are in Chinese.

Requires Windows, Python 3.12+, Git, Blender and a local licensed game installation. Offline smoke builds were run with Python 3.12.7 and Blender 5.2.3 LTS. Install DML, DMF and Custom Assets from their original publishers before using a generated mod.

```powershell
git clone https://github.com/Vionian/darktide-model-replacement.git
cd darktide-model-replacement
python tools/darktide.py install-skill
python tools/darktide.py setup
python tools/darktide.py doctor
```

Pass `setup --game "GAME_DIRECTORY" --blender "BLENDER_EXE"` if discovery fails. Updating an existing skill requires `--replace` and creates a backup. Reload your assistant's skills, open this repository and ask it to inspect your blend, adapt its skeleton/materials or weapon coordinates, compile and audit an isolated candidate, then package it. Pack textures or provide valid texture paths.

The assistant writes the model's profile and any required adapters. Arbitrary rigs/shaders are not guaranteed to work without changes. The human character baseline excludes Ogryn and advanced menu/HUD/costume integration. The weapon runtime targets sword-style attachment families. Default builds do not execute MMR hand authoring. Offline success does not prove in-game visuals or animation.

Game resources, source art, Oodle DLLs and unlicensed plugins are excluded. Setup downloads pinned upstream tools with SHA256 checks and extracts local skeleton references. Source blends remain unchanged. See [validation](docs/validation.md), [knowledge index](docs/knowledge-index.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Original code and docs: [GPL-3.0](LICENSE).
