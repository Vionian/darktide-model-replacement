"""Narrow runtime patch; preserve each installed provider's other adaptations."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def replace_once(code, old, new):
    assert code.count(old) == 1, (old, code.count(old))
    return code.replace(old, new)


def patch_provider(code):
    if 'preview_lifecycle.allowed(spawner)' in code:
        return code
    code = replace_once(code,
        '    if preview_lifecycle.blocked(spawner) then return end\n',
        '    if preview_lifecycle.blocked(spawner) then return end\n'
        '    if not preview_lifecycle.allowed(spawner) then\n'
        '        ui_despawn(spawner)\n'
        '        return\n'
        '    end\n')
    code = replace_once(code, 'preview_lifecycle.subject(spawner, unit, BODY)',
                        'preview_lifecycle.subject(spawner, unit, BODY, ui_despawn)')
    code = replace_once(code, 'local function apply(ext, first_person_mode)\n',
                        'local function apply(ext, first_person_mode)\n'
                        '    if preview_lifecycle.blocked(ext) then return end\n')
    for expression in ('body, not first_person_mode',
                       'arms, first_person_mode and true or false',
                       'parts[id], not first_person_mode',
                       'part_arms[id], first_person_mode and true or false'):
        unit, wanted = expression.split(', ', 1)
        code = replace_once(code, f'Unit.set_unit_visibility({expression}, true)',
                            f'preview_lifecycle.actor_subject({unit}, ext._unit, {wanted})')
    code = replace_once(code, 'local function delete_unit(unit, world)\n',
                        'local function delete_unit(unit, world)\n'
                        '    preview_lifecycle.release_actor(unit)\n')
    # Gameplay extension destruction can also reenter equipment visibility.
    match = re.search(r'(vl_hook\("destroy", function\(func, self, \.\.\.\)\n)(.*?)(\nend\))', code, re.S)
    assert match
    body = match[2]
    assert body.count('    return func(self, ...)') == 1
    cleanup = body.replace('    return func(self, ...)', '').rstrip()
    assert cleanup.startswith('    despawn(self)')
    cleanup = '\n'.join('    ' + line for line in cleanup.splitlines())
    code = code[:match.start()] + match[1] + (
        '    return preview_lifecycle.teardown(self, function(self)\n'
        + cleanup + '\n    end, func, ...)') + match[3] + code[match.end():]
    return code


def patch_controller(code):
    if 'local preview_lifecycle =' in code:
        return code
    code = replace_once(code, 'local mod = get_mod("AnimeModelReplacement")\n',
                        'local mod = get_mod("AnimeModelReplacement")\n'
                        'local preview_lifecycle = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/preview_lifecycle")\n'
                        'preview_lifecycle.install(mod)\n')
    for event in ('on_disabled', 'on_unload'):
        code = replace_once(code, f'mod.{event} = function()\n',
                            f'mod.{event} = function()\n\tpreview_lifecycle.reset()\n')
    return code


if __name__ == '__main__':
    for folder in sorted((ROOT / 'scripts/mods').iterdir()):
        if folder.name.endswith('Replacement'):
            path = folder / (folder.name + '.lua')
            code = path.read_text(encoding='utf-8-sig')
            patched = patch_controller(code) if folder.name == 'AnimeModelReplacement' else patch_provider(code)
            if patched != code:
                path.write_text(patched, encoding='utf-8')
                print(folder.name)
