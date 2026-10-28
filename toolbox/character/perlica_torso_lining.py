"""Source-specific, clothed interior for Perlica's otherwise open waist.

The authored mesh ends at the tights waistband and resumes under the chest.
This adds an opaque garment lining between those two actual boundary loops;
it does not reconstruct anatomy or alter the original exterior/hand surface.
"""
import collections
import numpy as np


def boundary_loop(mesh, material_index, height_range):
    mesh.data.calc_loop_triangles()
    world = np.asarray(mesh.matrix_world)
    points = np.array([(*v.co, 1.) for v in mesh.data.vertices]) @ world.T
    points = points[:, :3]
    _, welded = np.unique(np.round(points, 6), axis=0, return_inverse=True)
    tris = np.array([t.vertices[:] for t in mesh.data.loop_triangles
                     if t.material_index == material_index], dtype=int)
    edges = collections.Counter(tuple(sorted((int(a), int(b))))
                                for tri in welded[tris]
                                for a, b in zip(tri, np.roll(tri, -1)))
    graph = collections.defaultdict(set)
    for (a, b), count in edges.items():
        if count == 1:
            graph[a].add(b); graph[b].add(a)
    # Choose representatives from this material, not an unrelated coincident
    # vertex whose deform weights could differ at a clothing seam.
    representative = {int(welded[i]): int(i) for i in tris.ravel()}
    remaining = set(graph)
    candidates = []
    while remaining:
        stack = [remaining.pop()]; component = set(stack)
        while stack:
            for i in graph[stack.pop()]:
                if i in remaining:
                    remaining.remove(i); component.add(i); stack.append(i)
        ids = [representative[i] for i in component]
        p = points[ids]
        if p[:, 2].min() >= height_range[0] and p[:, 2].max() <= height_range[1]:
            assert all(len(graph[i]) == 2 for i in component), 'Open/branched source rim'
            ordered = [min(component)]
            previous = None
            while True:
                choices = graph[ordered[-1]] - ({previous} if previous is not None else set())
                nxt = min(choices)
                if nxt == ordered[0]:
                    break
                previous = ordered[-1]; ordered.append(nxt)
                assert len(ordered) <= len(component)
            assert len(ordered) == len(component)
            candidates.append(np.array([representative[i] for i in ordered]))
    assert len(candidates) == 1, (material_index, height_range, len(candidates))
    return candidates[0], points


def make_lining(mesh, positions, joints, weights):
    lower, source = boundary_loop(mesh, 10, (.98, 1.04))
    upper, _ = boundary_loop(mesh, 9, (1.23, 1.34))
    loops = []
    for ids in (lower, upper):
        xy = source[ids, :2]
        center = (xy.min(0) + xy.max(0)) * .5
        radius = (xy.max(0) - xy.min(0)) * .5
        theta = np.mod(np.arctan2((xy[:, 1]-center[1])/radius[1],
                                 (xy[:, 0]-center[0])/radius[0]), 2*np.pi)
        # Verify the polar order actually follows source boundary adjacency.
        steps = np.diff(np.unwrap(theta))
        assert np.all(steps > 0) or np.all(steps < 0), 'Non star-shaped source rim'
        order = np.argsort(theta)
        loops.append((ids[order], theta[order]))
    angles = np.unique(np.round(np.r_[loops[0][1], loops[1][1]], 9))
    all_palettes = sorted(set(int(j) for ids, _ in loops for j in joints[ids].ravel()))
    dense = np.zeros((len(positions), len(all_palettes)))
    for c, palette in enumerate(all_palettes):
        dense[:, c] = np.where(joints == palette, weights, 0).sum(1)
    ends = []
    for ids, theta in loops:
        a = np.r_[theta[-1]-2*np.pi, theta, theta[0]+2*np.pi]
        vid = np.r_[ids[-1], ids, ids[0]]
        i = np.searchsorted(a, angles, side='right') - 1
        t = ((angles-a[i])/(a[i+1]-a[i]))[:, None]
        ends.append(((1-t)*positions[vid[i]]+t*positions[vid[i+1]],
                     (1-t)*dense[vid[i]]+t*dense[vid[i+1]]))
    n = len(angles); rings = 7
    points = []; mass = []
    for v in np.linspace(0, 1, rings):
        p = (1-v)*ends[0][0]+v*ends[1][0]
        center = p[:, :2].mean(0)
        p[:, :2] = center+(p[:, :2]-center)*(1-.055*np.sin(np.pi*v))
        # End rings slightly overlap the inside of the original surfaces.
        # Their near-coincident seams are never exposed to the outside camera.
        if v == 0: p[:, 2] -= .003
        if v == 1: p[:, 2] += .003
        points.extend(p)
        mass.extend((1-v)*ends[0][1]+v*ends[1][1])
    points = np.asarray(points, np.float32); mass = np.asarray(mass)
    faces = []
    for r in range(rings-1):
        for i in range(n):
            j = (i+1) % n
            faces.extend(((r*n+i, r*n+j, (r+1)*n+j),
                          (r*n+i, (r+1)*n+j, (r+1)*n+i)))
    # A closed garment lining prevents a camera below the waist looking up
    # through the chest cavity and neck opening. Caps remain beneath clothing.
    for r in (0, rings-1):
        ids = np.arange(r*n, (r+1)*n)
        ci = len(points)
        points = np.r_[points, points[ids].mean(0, keepdims=True)]
        mass = np.r_[mass, mass[ids].mean(0, keepdims=True)]
        for i in range(n): faces.append((ci, int(ids[i]), int(ids[(i+1)%n])))
    faces = np.asarray(faces, dtype=int)
    centroid = points.mean(0)
    t = points[faces]; normals = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0])
    inward = np.sum(normals*(t.mean(1)-centroid), axis=1) < 0
    faces[inward] = faces[inward][:, [0, 2, 1]]
    normal = np.zeros_like(points)
    t = points[faces]; area = np.cross(t[:, 1]-t[:, 0], t[:, 2]-t[:, 0])
    for c in range(3): np.add.at(normal, faces[:, c], area)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    chosen = np.argsort(-mass, axis=1)[:, :4]
    w = np.take_along_axis(mass, chosen, axis=1)
    w /= w.sum(1, keepdims=True)
    j = np.asarray(all_palettes, np.uint8)[chosen]
    # Small, uniform brown textile area of the existing stocking diffuse.
    # Avoid the atlas's logos, glove islands and high-contrast seams.
    uv = np.c_[.10+.025*(np.arctan2(points[:, 1]-centroid[1], points[:, 0]-centroid[0])/(2*np.pi)+.5),
               .80+.03*(points[:, 2]-points[:, 2].min())/np.ptp(points[:, 2])]
    reversed_faces = faces[:, [0, 2, 1]]
    return dict(positions=points, joints=j, weights=w.astype(np.float32),
                faces=np.r_[faces, reversed_faces], uv=uv.astype(np.float32),
                normals=np.r_[normal[faces], -normal[reversed_faces]],
                outward_triangles=len(faces),
                source_boundary_vertices=[lower.tolist(), upper.tolist()])


def apply_to_groups(mesh, groups, arm_only):
    """Keep future body builds consistent with the installed surface-only fix."""
    if arm_only or mesh.data.materials[9].name != '肌' or mesh.data.materials[10].name != '丝袜':
        return groups
    g = groups[10]
    lining = make_lining(mesh, g['retargeted_positions'], g['joint_indices'], g['joint_weights'])
    nv = len(g['retargeted_positions']); nt = len(g['vertices'])
    # Restore the authored reverse surfaces only around the open hip interior.
    world = np.asarray(mesh.matrix_world)
    source = np.array([(*v.co, 1.) for v in mesh.data.vertices]) @ world.T
    reverse = g['triangles'][np.min(source[g['vertices'][g['triangles']], 2], axis=1) >= .84]
    old_vertices = g['vertices'][reverse][:, [0, 2, 1]]
    old_uv = g['uv'][reverse][:, [0, 2, 1]]
    old_normals = -g['normals'][reverse][:, [0, 2, 1]]
    g['vertices'] = np.r_[g['vertices'], old_vertices, lining['faces']+nv]
    g['uv'] = np.r_[g['uv'], old_uv, lining['uv'][lining['faces']]]
    g['normals'] = np.r_[g['normals'], old_normals, lining['normals']]
    g['triangles'] = np.r_[g['triangles'], np.arange(nt, len(g['vertices']))]
    for key, value in (('retargeted_positions', 'positions'), ('joint_indices', 'joints'), ('joint_weights', 'weights')):
        g[key] = np.r_[g[key], lining[value]]
    print('PERLICA_TORSO_LINING', lining['outward_triangles']*2, 'HIP_REVERSE', len(reverse))
    return groups
