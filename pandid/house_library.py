"""Export the maintained house stencils as an importable diagrams.net library.

The engine registry and this library consume the same artwork. Importing it
does not qualify the artwork or create canonical engineering records.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zlib

from pandid.render.house_artwork import ARTWORK


def library_xml() -> bytes:
    entries = []
    for key, art in sorted(ARTWORK.items()):
        compressor = zlib.compressobj(wbits=-15)
        shape = base64.b64encode(compressor.compress(art.stencil.encode()) + compressor.flush()).decode()
        model = ET.Element("mxGraphModel")
        root = ET.SubElement(model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        obj = ET.SubElement(root, "object", id="2", label="", **{
            "house-symbol": key, "house-symbol-version": art.version,
            "qualification": "candidate_requires_template_review",
            "reference-document": art.reference_document,
            "reference-sha256": art.reference_sha256,
        })
        cell = ET.SubElement(obj, "mxCell", vertex="1", parent="1",
                             style=f"shape=stencil({shape});aspect=fixed;fillColor=none;strokeColor=#111111;strokeWidth=2;")
        ET.SubElement(cell, "mxGeometry", width=str(art.width), height=str(art.height), **{"as": "geometry"})
        entries.append({"xml": ET.tostring(model, encoding="unicode"),
                        "w": art.width, "h": art.height, "title": key})
    library = ET.Element("mxlibrary")
    library.text = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
    return ET.tostring(library, encoding="utf-8", xml_declaration=True)


def export_library(destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(library_xml())
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    print(export_library(args.out))


if __name__ == "__main__":
    main()
