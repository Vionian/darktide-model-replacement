"""Compare previous/fixed compiled units, proving geometry is unchanged."""
import importlib.util
import pathlib
import sys
import json
import numpy as np

here = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("builder", here / "build_roshia_native.py")
b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = b
spec.loader.exec_module(b)
result = {}
for asset in ("roshia", "roshia_arms"):
    units = [b.unit_dt.UnitResourceDT(b.Cursor(str(here / "roshia" / candidate / "Custom" / asset / (asset + ".unit"))))
             for candidate in ("native_texture_candidate", "trs_fix_candidate")]
    old, new = units
    same = len(old.mesh_geometries) == len(new.mesh_geometries) and all(
        len(a.streams) == len(c.streams) and all(x.vertex_data == y.vertex_data for x, y in zip(a.streams, c.streams))
        and np.array_equal(a.index_stream.get_indices(), c.index_stream.get_indices())
        for a, c in zip(old.mesh_geometries, new.mesh_geometries))
    if not same:
        raise ValueError("Geometry changed during local TRS fix")
    texture_files = list((here / "roshia/trs_fix_candidate/Custom" / asset).glob("*.texture"))
    textures_same = all(path.read_bytes() == (here / "roshia/native_texture_candidate/Custom" / asset / path.name).read_bytes()
                        for path in texture_files)
    if not textures_same:
        raise ValueError("Texture changed during local TRS fix")
    result[asset] = {"geometry_streams_and_indices_identical": same, "texture_resources_identical": textures_same,
                     "texture_count": len(texture_files)}
(here / "roshia/trs_fix_candidate/geometry_preservation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("GEOMETRY_PRESERVATION " + json.dumps(result))
