"""Circle H2O process drawing conventions; no database or calculation authority.

Callers supply immutable engineering records and opaque source bindings.
All geometry is produced by pandid's units, layout, routing and exporters.
"""

from __future__ import annotations

import textwrap

from pandid import Annotation, Block, Flowsheet


STREAM_INK = {
    "recycle": ("#2874A6", "6 3"), "return": ("#2874A6", "6 3"),
    "sludge": ("#7D6608", "none"), "solids": ("#7D6608", "none"),
    "brine": ("#B9770E", "none"), "reject": ("#B9770E", "none"),
    "concentrate": ("#B9770E", "none"), "regeneration_waste": ("#B9770E", "none"),
}


def block_diagram(name: str, blocks: list[dict], streams: list[dict], *,
                  title_block, page_id: str, graph_attributes: dict,
                  print_scale: float = 2.7) -> Flowsheet:
    """Build canonical blocks, retaining numbers, names and every stream.

    Lane numbers are optional row constraints. Absolute positions and the old
    lane-grid/router output are deliberately not inputs to this adapter.
    """
    fs = Flowsheet(name)
    fs.title_block = title_block
    fs.print_scale = print_scale
    fs.layout_options.column_gap = 65.0
    fs.layout_options.row_gap = 45.0
    fs.layout_options.band_gap = 85.0
    fs.layout_options.band_width = 1900.0
    fs.stream_labels.enclosure = "none"
    records = {row["key"]: row for row in blocks}
    if len(records) != len(blocks):
        raise ValueError("duplicate BFD block identity")
    if len({row["key"] for row in streams}) != len(streams):
        raise ValueError("duplicate BFD stream identity")
    ends = {key: {"in": [], "out": []} for key in records}
    for row in streams:
        ends[row["source"]]["out"].append(row["key"])
        ends[row["target"]]["in"].append(row["key"])
    units = {}
    bindings = {"page_id": page_id, "graph": graph_attributes, "units": {}, "streams": {},
                "cells": {
                    "f0": {"id": "circle-h2o-title-block", "attributes": {
                        "puran-kind": "engineering-title-block"}},
                    "z-frame": {"id": "sheet-border", "attributes": {
                        "puran-kind": "engineering-sheet-frame"}},
                    "z-sheet": {"id": "sheet-paper", "attributes": {
                        "puran-kind": "engineering-sheet-background"}},
                    "f1": {"id": "bfd-stream-legend", "attributes": {
                        "puran-kind": "engineering-legend"}},
                }}
    for key, row in records.items():
        incoming, outgoing = ends[key]["in"], ends[key]["out"]
        block = Block(key, inputs=len(incoming), outputs=len(outgoing), label_pos="center")
        lines = []
        for line in row["label"].splitlines():
            lines.extend(textwrap.wrap(line, width=23, break_long_words=False,
                                       break_on_hyphens=False) or [""])
        block.display_label = "\n".join(lines)
        if row.get("lane_index") is not None:
            block.pin(row=row["lane_index"])
        units[key] = fs.add(block)
        bindings["units"][key] = {"id": row["id"], "attributes": row["attributes"]}
    for row in streams:
        source, target = row["source"], row["target"]
        line = fs.connect(units[source].outlets[ends[source]["out"].index(row["key"])],
                          units[target].inlets[ends[target]["in"].index(row["key"])],
                          name=row["key"])
        line.color, line.dasharray = STREAM_INK.get(row.get("service"), ("#34495E", "none"))
        if row.get("held"):
            line.color, line.dasharray = "#C0392B", "6 3"
        bindings["streams"][line.name] = {"id": row["id"], "attributes": row["attributes"]}
        if row.get("label", line.name) != line.name:
            line.display_label = row["label"]
    treatments = {}
    for row in streams:
        color, pattern = ("#C0392B", "6 3") if row.get("held") else STREAM_INK.get(row.get("service"), ("#34495E", "none"))
        treatments.setdefault((color, pattern), set()).add(row.get("service") or "process")
    fs.add_annotation(Annotation(title="STREAM KEY", align="bottom-left", font_size=7.5,
        rows=[("", ", ".join(sorted(names)).replace("_", " ")) for names in treatments.values()],
        line_samples=[{"color": color, "dasharray": pattern, "arrow": True} for color, pattern in treatments]))
    fs.drawio_metadata = bindings
    return fs
