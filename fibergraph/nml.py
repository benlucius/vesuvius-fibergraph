from __future__ import annotations

from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

from .models import FiberGraphNML, FiberInstance


def _f(x: str | None, default: float = 1.0) -> float:
    return default if x is None else float(x)


def read_nml(path: str | Path) -> FiberGraphNML:
    """Read the WebKnossos NML flavor used by ScrollPrize fiber skeletons.

    Coordinates are preserved in NML XYZ voxel coordinates. Physical scale is
    returned separately in ``FiberGraphNML.scale_xyz``.
    """
    root = ET.parse(path).getroot()
    scale = root.find("./parameters/scale")
    if scale is not None:
        scale_xyz = (_f(scale.get("x")), _f(scale.get("y")), _f(scale.get("z")))
        unit = scale.get("unit") or "voxel"
    else:
        scale_xyz, unit = (1.0, 1.0, 1.0), "voxel"

    fibers: list[FiberInstance] = []
    for thing in root.findall("./thing"):
        nodes: dict[str, np.ndarray] = {}
        for n in thing.findall("./nodes/node"):
            nid = n.get("id")
            if nid is None:
                continue
            nodes[nid] = np.array([float(n.get("x")), float(n.get("y")), float(n.get("z"))], dtype=np.float64)
        edges: list[tuple[str, str]] = []
        for e in thing.findall("./edges/edge"):
            a, b = e.get("source"), e.get("target")
            if a in nodes and b in nodes:
                edges.append((a, b))
        if nodes and edges:
            fibers.append(FiberInstance(
                fiber_id=thing.get("id") or str(len(fibers)),
                name=thing.get("name") or "",
                nodes=nodes,
                edges=tuple(edges),
            ))
    return FiberGraphNML(tuple(fibers), scale_xyz=scale_xyz, unit=unit)


def write_nml(graph: FiberGraphNML, path: str | Path) -> None:
    root = ET.Element("things")
    params = ET.SubElement(root, "parameters")
    sx, sy, sz = graph.scale_xyz
    ET.SubElement(params, "scale", x=str(sx), y=str(sy), z=str(sz), unit=graph.unit)
    next_node = 1
    for i, fiber in enumerate(graph.fibers, start=1):
        thing = ET.SubElement(root, "thing", id=str(fiber.fiber_id), name=fiber.name or f"fiber_{i}")
        ns = ET.SubElement(thing, "nodes")
        es = ET.SubElement(thing, "edges")
        # Preserve original IDs if possible, otherwise allocate stable IDs.
        id_map: dict[str, str] = {}
        for old_id, xyz in fiber.nodes.items():
            nid = str(old_id) if str(old_id).isdigit() else str(next_node)
            next_node = max(next_node + 1, int(nid) + 1 if nid.isdigit() else next_node + 1)
            id_map[old_id] = nid
            ET.SubElement(ns, "node", id=nid, radius="1", x=f"{xyz[0]:.6g}", y=f"{xyz[1]:.6g}", z=f"{xyz[2]:.6g}")
        for a, b in fiber.edges:
            if a in id_map and b in id_map:
                ET.SubElement(es, "edge", source=id_map[a], target=id_map[b])
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def fiber_paths(fiber: FiberInstance) -> list[np.ndarray]:
    """Decompose a fiber graph into maximal non-branching paths.

    This is robust to occasional branch annotations. A pure path returns one
    ordered polyline. Cycles are broken deterministically at the smallest node id.
    """
    adj: dict[str, list[str]] = {k: [] for k in fiber.nodes}
    for a, b in fiber.edges:
        if a in adj and b in adj:
            adj[a].append(b); adj[b].append(a)
    seen: set[frozenset[str]] = set()
    critical = sorted([k for k, v in adj.items() if len(v) != 2], key=str)
    paths: list[np.ndarray] = []

    def walk(start: str, nxt: str) -> list[str]:
        ids = [start, nxt]
        prev, cur = start, nxt
        seen.add(frozenset((start, nxt)))
        while len(adj[cur]) == 2:
            cand = adj[cur][0] if adj[cur][1] == prev else adj[cur][1]
            key = frozenset((cur, cand))
            if key in seen:
                break
            ids.append(cand)
            seen.add(key)
            prev, cur = cur, cand
        return ids

    for start in critical:
        for nxt in sorted(adj[start], key=str):
            if frozenset((start, nxt)) not in seen:
                ids = walk(start, nxt)
                paths.append(np.stack([fiber.nodes[k] for k in ids]))

    # Remaining edges belong to cycles or disconnected degree-2 components.
    for a, b in sorted(fiber.edges, key=lambda e: (str(e[0]), str(e[1]))):
        if frozenset((a, b)) in seen:
            continue
        ids = walk(a, b)
        paths.append(np.stack([fiber.nodes[k] for k in ids]))
    return paths
