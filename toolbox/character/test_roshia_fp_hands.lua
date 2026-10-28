-- The first-person unit is driven by Darktide's native named-node animation.
-- This probe prevents the legacy duplicate override beside source-hand FK.
local source = assert(io.open("scripts/mods/RoshiaReplacement/fp_hands.lua", "r")):read("*a")
assert(not source:find("Unit%.set_local_rotation"), "FP hand module must not write native finger rotations")
assert(source:find("function M%.update"), "FP hand compatibility module is missing update")
assert(loadfile("scripts/mods/RoshiaReplacement/fp_hands.lua"), "FP hand module must parse as Lua")
local replacement = assert(io.open("scripts/mods/RoshiaReplacement/RoshiaReplacement.lua", "r")):read("*a")
assert(not replacement:find("fp_hands%.update"), "Roshia runtime must not install the legacy finger override")
assert(replacement:find("proportion_rig%.update%(unit, parent, proportion_config%.arms%)"),
    "first-person arms must use the source-hand FK rig")
assert(not replacement:find("World%.link_unit%(world, unit, 1, parent, 1, World%.LINK_MODE_NODE_NAME%)"),
    "first-person node linking would overwrite authored source finger pivots")
assert(replacement:find("proportion_rig%.update%(self%.__roshia_arms, self%._first_person_unit, proportion_config%.arms%)"),
    "first-person FK must follow the live animation driver each frame")
assert(loadfile("scripts/mods/RoshiaReplacement/RoshiaReplacement.lua"), "Roshia runtime must parse as Lua")
print("FP_HAND_NATIVE_DRIVER_ONLY_OK")
