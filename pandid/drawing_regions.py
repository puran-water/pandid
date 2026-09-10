"""Engine-owned labelled regions and captions, shared by both exporters.

Regions are drawing furniture within the process area, not process units or
router obstacles. Their bounds participate in page fitting. They cannot carry
ports, replace a stream, or supply engineering values.
"""
from dataclasses import asdict, dataclass
from html import escape
import math
import xml.etree.ElementTree as ET
from pandid.render.furniture import text_width


@dataclass(frozen=True)
class Region:
    key: str
    x: float
    y: float
    w: float
    h: float
    title: str = ""
    font_size: float = 18
    stroke: str = "#D5DBDB"


@dataclass(frozen=True)
class Caption:
    key: str
    x: float
    y: float
    w: float
    h: float
    text: str
    font_size: float = 12
    bold: bool = False


def validate(fs):
    keys = set()
    for item in [*fs.regions, *fs.captions]:
        if not item.key or item.key in keys:
            raise ValueError("Drawing regions and captions need unique nonempty keys")
        keys.add(item.key)
        if any(not math.isfinite(v) for v in (item.x, item.y, item.w, item.h, item.font_size)) or min(item.w, item.h, item.font_size) <= 0:
            raise ValueError("Drawing region geometry must be finite with positive dimensions")


def bounds(fs, inner):
    validate(fs)
    rectangles = [inner] + [(r.x, r.y, r.x + r.w, r.y + r.h) for r in [*fs.regions, *fs.captions]]
    return (min(r[0] for r in rectangles), min(r[1] for r in rectangles),
            max(r[2] for r in rectangles), max(r[3] for r in rectangles))


def captions(fs):
    return [Caption(r.key + "-heading", r.x + 10, r.y + 4, min(r.w - 20, text_width(r.title, r.font_size, bold=True) + 6),
                    r.font_size * 1.5, r.title, r.font_size, True)
            for r in fs.regions if r.title] + list(fs.captions)


def drawio(fs, fit):
    result = []
    for r in [*fs.regions, *captions(fs)]:
        is_text = isinstance(r, Caption)
        style = (f"text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=top;spacing=0;whiteSpace=wrap;"
                 f"fontSize={fit.length(r.font_size):g};fontStyle={1 if r.bold else 0};fontFamily=Arial;fontColor=#263238;"
                 if is_text else f"rounded=0;strokeColor={r.stroke};fillColor=none;strokeWidth={fit.length(.65):g};")
        cell = ET.Element("mxCell", id="region-" + r.key, value="<br>".join(escape(line) for line in r.text.splitlines()) if is_text else "",
                          style=style, vertex="1", parent="1")
        x, y = fit.at(r.x, r.y)
        ET.SubElement(cell, "mxGeometry", {"x": f"{x:g}", "y": f"{y:g}", "width": f"{fit.length(r.w):g}",
                                            "height": f"{fit.length(r.h):g}", "as": "geometry"})
        result.append(ET.tostring(cell, encoding="unicode"))
    return result


def svg(fs):
    result = []
    for r in fs.regions:
        result.append(f'<rect x="{r.x:g}" y="{r.y:g}" width="{r.w:g}" height="{r.h:g}" fill="none" stroke="{escape(r.stroke)}" stroke-width=".65"/>')
    for c in captions(fs):
        for n, line in enumerate(c.text.splitlines()):
            result.append(f'<text x="{c.x:g}" y="{c.y + c.font_size * (1 + n * 1.2):g}" font-size="{c.font_size:g}" font-family="Arial" font-weight="{"bold" if c.bold else "normal"}">{escape(line)}</text>')
    return result


def read(fs, data):
    fs.regions = [Region(**r) for r in data.get("regions", [])]
    fs.captions = [Caption(**r) for r in data.get("captions", [])]
    validate(fs)


def write(fs):
    validate(fs)
    return {key: [asdict(r) for r in getattr(fs, key)] for key in ("regions", "captions") if getattr(fs, key)}
