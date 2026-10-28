"""Build one Endfield candidate into an explicit isolated output directory."""
import argparse
import pathlib
import sys

here = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from endfield_profiles import PROFILES, apply
import build_roshia_native as builder

parser = argparse.ArgumentParser()
parser.add_argument("profile", choices=tuple(PROFILES))
parser.add_argument("--output", type=pathlib.Path, required=True)
script_args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
args, rest = parser.parse_known_args(script_args)

apply(builder, args.profile)
builder.OUTPUT = args.output.resolve()
builder.HAND_AUTHORING_OUTPUT = builder.OUTPUT.parent
builder.OUTPUT.mkdir(parents=True, exist_ok=True)
builder.HAND_AUTHORING_OUTPUT.mkdir(parents=True, exist_ok=True)
sys.argv = [sys.argv[0], "--", "--asset-prefix", args.profile,
            "--source-blend", str(builder.SOURCE_BLEND),
            "--resource-root", builder.RESOURCE_ROOT,
            "--mesh-object", builder.MESH_OBJECT_NAME,
            "--armature-object", builder.ARMATURE_OBJECT_NAME,
            "--scale", str(builder.SCALE), "--output-dir", str(builder.OUTPUT),
            "--runtime-config-output", str(builder.OUTPUT / (args.profile + "_jiggle_bones.lua"))] + rest
builder.main()
