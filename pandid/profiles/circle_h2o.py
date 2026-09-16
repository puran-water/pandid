"""Circle H2O process drawing conventions; no database or calculation authority.

Callers supply immutable engineering records and opaque source bindings.
All geometry is produced by pandid's units, layout, routing and exporters.
"""

from __future__ import annotations

import math
import textwrap

from pandid import Annotation, Block, Flowsheet


STREAM_INK = {
    "recycle": ("#2874A6", "6 3"), "return": ("#2874A6", "6 3"),
    "sludge": ("#7D6608", "none"), "solids": ("#7D6608", "none"),
    "brine": ("#B9770E", "none"), "reject": ("#B9770E", "none"),
    "concentrate": ("#B9770E", "none"), "regeneration_waste": ("#B9770E", "none"),
}
_PX_PER_MM = 96.0 / 25.4
_FURNITURE_PRINT_SCALE = 2.7


def _paper_mm_in_nominal_units(value, print_scale, name):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError(f'{name} must be positive and finite')
    if (isinstance(print_scale, bool) or not isinstance(print_scale, (int, float))
            or not math.isfinite(print_scale) or print_scale <= 0):
        raise ValueError('print_scale must be positive and finite')
    return value * _PX_PER_MM / print_scale


def plan_block_diagram(blocks, streams, lanes, *, print_scale: float = 2.7,
                       band_width: float = 2100.0,
                       column_gap_mm: float = 12.0,
                       row_gap_mm: float = 10.0,
                       band_gap_mm: float = 14.0):
    """Return the measured lane plan used by :func:`block_diagram`.

    ``band_width`` and the returned extents are nominal CSS-pixel units.
    Clearances are stated on paper and converted through ``print_scale``.
    """
    from pandid.layout.block_lanes import plan_details
    return plan_details(
        blocks, streams, lanes, band_width=band_width,
        column_gap=_paper_mm_in_nominal_units(
            column_gap_mm, print_scale, 'column_gap_mm'),
        row_gap=_paper_mm_in_nominal_units(row_gap_mm, print_scale, 'row_gap_mm'),
        band_gap=_paper_mm_in_nominal_units(band_gap_mm, print_scale, 'band_gap_mm'))


def block_diagram(name: str, blocks: list[dict], streams: list[dict], *,
                  title_block, page_id: str, graph_attributes: dict,
                  print_scale: float = 2.7, band_width: float = 2100.0,
                  column_gap_mm: float = 12.0, row_gap_mm: float = 10.0,
                  band_gap_mm: float = 14.0,
                  lanes=None) -> Flowsheet:
    """Build canonical blocks, retaining numbers, names and every stream.

    Ordered lane membership and optional per-lane size scales are semantic
    input. Grid placement, nozzle faces and visible lane bands are engine
    decisions.
    """
    fs = Flowsheet(name)
    fs.title_block = title_block
    column_gap = _paper_mm_in_nominal_units(
        column_gap_mm, print_scale, 'column_gap_mm')
    row_gap = _paper_mm_in_nominal_units(
        row_gap_mm, print_scale, 'row_gap_mm')
    band_gap = _paper_mm_in_nominal_units(
        band_gap_mm, print_scale, 'band_gap_mm')
    # Sheet furniture is qualified at this fixed paper scale.  The caller's
    # fitted scale applies only to the content group; sharing it with the page
    # would shrink title-strip, legend and zone lettering along with the BFD.
    fs.print_scale = _FURNITURE_PRINT_SCALE
    fs.drawing_scale = print_scale / _FURNITURE_PRINT_SCALE
    fs.layout_options.stream_spacing = 14
    # BFD reviews must not spend a congested caption's clearance by putting
    # its white plate through a process block. Use the existing clear-paper
    # fallback, with a leader and with text included in the sheet envelope.
    fs.layout_options.strict_label_clearance = True
    fs.layout_options.column_gap = column_gap
    fs.layout_options.row_gap = row_gap
    fs.layout_options.band_gap = band_gap
    fs.layout_options.band_width = band_width
    fs.stream_labels.enclosure = "none"
    fs.stream_labels.font_size = 14.5
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
    lane_plan = None
    if lanes:
        lane_plan = plan_block_diagram(
            blocks, streams, lanes, print_scale=print_scale,
            band_width=band_width, column_gap_mm=column_gap_mm,
            row_gap_mm=row_gap_mm, band_gap_mm=band_gap_mm)
        pins, fs.regions, faces, labels = (lane_plan.positions, lane_plan.regions,
                                          lane_plan.faces, lane_plan.labels)
        fs.stream_labels.font_size = 22
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
        block = Block(key, inputs=faces[key]['in'] if lane_plan else len(incoming),
                      outputs=faces[key]['out'] if lane_plan else len(outgoing), label_pos="center",
                      width=lane_plan.sizes[key][0] if lane_plan else None,
                      height=lane_plan.sizes[key][1] if lane_plan else None,
                      font_size=22 if lane_plan else 12)
        lines = []
        for line in row["label"].splitlines():
            lines.extend(textwrap.wrap(line, width=23, break_long_words=False,
                                       break_on_hyphens=False) or [""])
        block.display_label = labels[key] if lane_plan else "\n".join(lines)
        if lane_plan:
            block.pin(**pins[key])
        elif row.get("lane_index") is not None:
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
    for region in fs.regions:
        bindings['cells']['region-' + region.key] = {'id': 'bfd-' + region.key,
            'attributes': {'puran-kind': 'bfd-lane', 'puran-lane': region.key.removeprefix('lane-')}}
        bindings['cells']['region-' + region.key + '-heading'] = {'id': 'bfd-' + region.key + '-heading',
            'attributes': {'puran-kind': 'bfd-lane-heading', 'puran-lane': region.key.removeprefix('lane-')}}
    return fs
