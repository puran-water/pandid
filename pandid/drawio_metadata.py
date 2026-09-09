"""Stable appearances and opaque source bindings for editable drawing exports.

Engineering databases own the meaning of these attributes. Pandid carries them
without interpreting them, alongside the geometry it generates. This keeps a
renamed appearance addressable by revision tools without using its visible tag
or its position in the input list as its identity.
"""

from __future__ import annotations

from copy import deepcopy
import json
import re
import xml.etree.ElementTree as ET


def physical_page(document: str, sheet) -> str:
    """Convert CSS geometry into draw.io's 100 units/inch physical paper.

    The diagram and native furniture keep their proportions. Relative terminal
    fractions, edge-label fractions and table structure are never rescaled.
    """
    factor = sheet.print_scale * 100 / 96
    tree = ET.fromstring(document)
    graph = tree.find("diagram/mxGraphModel")
    graph.set("pageWidth", str(round(sheet.width_mm * 100 / 25.4)))
    graph.set("pageHeight", str(round(sheet.height_mm * 100 / 25.4)))
    lengths = {"fontSize", "strokeWidth", "spacing", "spacingTop", "spacingBottom",
               "spacingLeft", "spacingRight", "startSize", "endSize", "jumpSize",
               "labelWidth", "exitDx", "exitDy", "entryDx", "entryDy"}
    for cell in graph.iter("mxCell"):
        style = []
        for entry in cell.get("style", "").split(";"):
            key, sep, value = entry.partition("=")
            if sep and key in lengths:
                try:
                    value = f"{float(value) * factor:.6g}"
                except ValueError:
                    pass
            style.append(key + sep + value)
        if cell.get("style") is not None:
            cell.set("style", ";".join(style))
        if cell.get("value"):
            cell.set("value", re.sub(r"font-size:\s*([\d.]+)px",
                     lambda m: f"font-size:{float(m[1]) * factor:.6g}px", cell.get("value")))
    for geometry in [*graph.iter("mxGeometry"), *graph.iter("mxRectangle")]:
        for key in ("x", "y", "width", "height"):
            if key in geometry.attrib and not (geometry.get("relative") == "1" and key in {"x", "y"}):
                geometry.set(key, f"{float(geometry.get(key)) * factor:.6f}")
    for point in graph.iter("mxPoint"):
        for key in ("x", "y"):
            if key in point.attrib:
                point.set(key, f"{float(point.get(key)) * factor:.6f}")
    return ET.tostring(tree, encoding="unicode") + "\n"


def validate_bindings(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("drawio_metadata must be a mapping")
    unknown = set(value) - {"page_id", "page", "graph", "layer", "units", "streams", "cells"}
    if unknown:
        raise ValueError(f"unknown drawio_metadata keys: {sorted(unknown)}")
    if "page_id" in value and (not isinstance(value["page_id"], str) or not value["page_id"]):
        raise ValueError("page_id must be a nonempty string")
    for field in ("units", "streams", "cells"):
        if not isinstance(value.get(field, {}), dict):
            raise ValueError(f"drawio_metadata.{field} must be a mapping")
        for key, entry in value.get(field, {}).items():
            if not isinstance(key, str) or not isinstance(entry, dict):
                raise ValueError(f"drawio_metadata.{field} needs named bindings")
            if set(entry) - {"id", "attributes", "label"}:
                raise ValueError(f"unknown drawing binding fields: {field}.{key}")
            if not isinstance(entry.get("id", key), str) or not entry.get("id", key):
                raise ValueError(f"drawing appearance needs a nonempty id: {key}")
            _attributes(entry.get("attributes", {}))
    for field in ("page", "graph", "layer"):
        _attributes(value.get(field, {}))
    # Reject nonfinite numbers and non-JSON payloads before a render starts.
    json.dumps(value, allow_nan=False)
    return deepcopy(value)


def _attributes(value: dict) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("drawing attributes must be a mapping")
    reserved = {"id", "label", "value", "style", "parent", "source", "target", "vertex", "edge"}
    if set(value) & reserved:
        raise ValueError("source attributes cannot replace drawing structure")
    result = {}
    for key, item in value.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", key):
            raise ValueError(f"invalid drawing attribute name: {key!r}")
        if item is not None:
            result[key] = item if isinstance(item, str) else json.dumps(item, sort_keys=True)
    return result


def apply_bindings(document: str, fs) -> str:
    bindings = validate_bindings(getattr(fs, "drawio_metadata", {}))
    if not bindings:
        return document
    tree = ET.fromstring(document)
    page = tree.find("diagram")
    graph = page.find("mxGraphModel")
    root = graph.find("root")
    if bindings.get("page_id"):
        page.set("id", bindings["page_id"])
    page.attrib.update(_attributes(bindings.get("page", {})))
    graph_values = _attributes(bindings.get("graph", {}))
    # Native graph options stay on mxGraphModel; source metadata belongs on an
    # mxGraph user-object wrapper, accepted by the diagrams.net XSD.
    custom = {key: value for key, value in graph_values.items() if key.startswith("puran-")}
    graph.attrib.update({key: value for key, value in graph_values.items() if key not in custom})
    if custom:
        bindings["layer"] = {**custom, **bindings.get("layer", {})}
    entries = dict(bindings.get("cells", {}))
    for field, objects, prefix in (("units", fs.units, "u"), ("streams", fs.streams, "s")):
        names = {obj.name for obj in objects}
        missing = set(bindings.get(field, {})) - names
        if missing:
            raise ValueError(f"drawing bindings name absent {field}: {sorted(missing)}")
        for index, obj in enumerate(objects):
            if obj.name in bindings.get(field, {}):
                entries[f"{prefix}{index}"] = bindings[field][obj.name]
    # Instrument stems follow the balloon's stable appearance identity.
    from pandid.render.svg import tap_lines
    for n, (instrument, _tap, _centre) in enumerate(tap_lines(fs)):
        owner = bindings.get("units", {}).get(instrument.name)
        if owner and owner.get("id"):
            entries[f"t{n}"] = {"id": owner["id"] + "-tap", "attributes": {
                "puran-kind": "appearance-detail", "for-cell": owner["id"]}}
    if bindings.get("layer"):
        entries["1"] = {"attributes": bindings["layer"]}
    ids = {}
    owners = {}
    for cell in root:
        old = cell.get("id")
        parent_key = next((key for key in sorted(entries, key=len, reverse=True) if old == key or old.startswith(key + "-") or (re.fullmatch(r"s\d+", key) and re.fullmatch(re.escape(key) + r"h\d+", old))), None)
        ids[old] = (entries[parent_key].get("id", parent_key) + old[len(parent_key):]
                    if parent_key is not None else old)
        owners[old] = parent_key
    if len(set(ids.values())) != len(ids):
        raise ValueError("duplicate stable drawing appearance identity")
    for index, cell in enumerate(list(root)):
        old = cell.get("id")
        cell.set("id", ids[old])
        for attr in ("parent", "source", "target"):
            if cell.get(attr) in ids:
                cell.set(attr, ids[cell.get(attr)])
        entry = entries.get(old)
        if entry is None and owners[old] is not None:
            owner = entries[owners[old]]
            kind = owner.get("attributes", {}).get("puran-kind")
            if kind:
                entry = {"attributes": {
                    "puran-kind": "legend-entry" if kind == "engineering-legend" else "appearance-detail",
                    "for-cell": owner.get("id", owners[old]),
                }}
        if entry is None and old not in {"0", "1"}:
            entry = {"attributes": {"puran-kind": "engineering-sheet-frame" if re.fullmatch(r"z\d+", old) else "appearance-detail"}}
        if entry is None:
            continue
        attrs = _attributes(entry.get("attributes", {}))
        if "label" in entry:
            cell.set("value", str(entry["label"]))
        if attrs:
            wrapper = ET.Element("object", {
                "id": cell.attrib.pop("id"), "label": cell.attrib.pop("value", ""), **attrs})
            wrapper.append(cell)
            root.remove(cell)
            root.insert(index, wrapper)
    return ET.tostring(tree, encoding="unicode") + "\n"
