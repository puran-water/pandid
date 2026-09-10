"""Bounded, JSON discovery of the installed engine for CLI and agent adapters.

Catalogues and constructors come from the same classes and symbol registry used
by the spec reader. No database, render job or remote documentation is required.
"""
from __future__ import annotations

import argparse
from difflib import get_close_matches
import inspect
import json

from pandid import Flowsheet
from pandid import spec
from pandid.render.symbols import default_registry


def _page(rows, *, offset=0, limit=20):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("offset must be nonnegative and limit must be between 1 and 100")
    return {"total": len(rows), "offset": offset, "limit": limit,
            "next_offset": offset + limit if offset + limit < len(rows) else None,
            "items": rows[offset:offset + limit]}


def _class(name):
    resolved = spec._ALIASES.get(name.strip().lower())
    if resolved is None:
        suggestions = get_close_matches(name, sorted(spec._CLASSES), n=3)
        raise ValueError(f"Unknown unit class {name!r}; suggestions: {suggestions}; use catalog()")
    return spec._CLASSES[resolved]


def _variants(cls):
    available = default_registry.variants(cls.kind)
    if cls.VARIANTS:
        aliases = getattr(cls, "VARIANT_ALIASES", {})
        return [v for v in cls.VARIANTS if aliases.get(v, v) in available]
    return available


def catalog(*, query=None, offset=0, limit=20):
    """List spec-readable unit classes without artwork or full parameter records."""
    needle = (query or "").casefold()
    rows = []
    for name, cls in sorted(spec._CLASSES.items()):
        variants = _variants(cls)
        if needle and needle not in " ".join([name, cls.kind, *variants]).casefold():
            continue
        rows.append({"key": name, "kind": cls.kind,
                     "spec_section": "instruments" if cls.kind == "instrument" else "units",
                     "variant_count": len(variants),
                     "matched_variants": [v for v in variants if needle and needle in v.casefold()]})
    return _page(rows, offset=offset, limit=limit)


def describe_unit(name, *, variant="default", parameters=None):
    """Resolve the requested constructor and return its actual named ports.

    Variable port families are instantiated with the supplied counts. The
    returned defaults describe this synthetic object, never equipment sizing.
    """
    cls = _class(name)
    values = dict(parameters or {})
    if {"name", "variant"} & values.keys():
        raise ValueError("name and variant are supplied separately from parameters")
    signature = inspect.signature(cls)
    declared = []
    for key, param in signature.parameters.items():
        if key in {"name", "variant"}:
            continue
        if param.kind in {param.VAR_KEYWORD, param.VAR_POSITIONAL}:
            declared.append({"name": key, "variadic": True})
            continue
        row = {"name": key, "required": param.default is param.empty,
               "annotation": str(param.annotation) if param.annotation is not param.empty else None}
        if param.default is not param.empty:
            default = param.default
            row["default"] = default if isinstance(default, (str, int, float, bool, list, tuple, dict, type(None))) else repr(default)
        declared.append(row)
    tag = "250-FIT-01" if cls.kind == "instrument" else "DISCOVERY-UNIT"
    unit = cls(tag, variant=variant, **values)
    symbol = default_registry.for_unit(unit)
    return {"key": cls.__name__, "kind": cls.kind, "variant": unit.variant,
            "accepted_variants": _variants(cls), "parameters": declared,
            "ports": [{"name": p.name, "direction": p.direction, "role": p.role}
                      for p in unit.ports.values()],
            "symbol": {"native_shape": symbol.drawio_shape,
                       "width": symbol.width, "height": symbol.height,
                       "gravity_fixed": symbol.gravity_fixed,
                       "faceless_ports": sorted(symbol.faceless_ports)},
            "spec_section": "instruments" if cls.kind == "instrument" else "units",
            "basis": "Synthetic constructor inspection; sizes and counts are not project engineering data"}


EXAMPLES = {
    "magnetic-control-loop": "Inline magnetic primary, stem/FIT, shared FIC and pneumatic valve actuator",
    "parallel-pumps": "Three rotary-lobe pump branches between connected pipe headers",
    "bfd-lanes": "Uniform blocks in two labelled process roll-up lanes",
}


def example(key):
    """A small executable spec illustrating one engine capability."""
    from pandid import Feed, Fitting, Instrument, Junction, Product, Pump, Valve
    if key not in EXAMPLES:
        raise ValueError(f"Unknown example {key!r}; choose one of {sorted(EXAMPLES)}")
    if key == "bfd-lanes":
        from pandid.profiles.circle_h2o import block_diagram
        blocks = [
            {"key": "headworks", "label": "104\nHeadworks Screening", "lane": "pretreatment", "order": 1},
            {"key": "equalisation", "label": "120\nEqualisation", "lane": "pretreatment", "order": 2},
            {"key": "mbr", "label": "250\nMembrane Bioreactor", "lane": "biological", "order": 3},
        ]
        streams = [
            {"key": "104-01", "source": "headworks", "target": "equalisation", "label": "104-01"},
            {"key": "120-01", "source": "equalisation", "target": "mbr", "label": "120-01"},
        ]
        for row in [*blocks, *streams]:
            row.update(id="example-" + row["key"], attributes={"synthetic": True})
        fs = block_diagram("SYNTHETIC BFD LANES", blocks, streams,
                          title_block=None, page_id="example-bfd-lanes",
                          graph_attributes={"synthetic": True},
                          lanes=[{"id": "pretreatment", "title": "Pre-Treatment"},
                                 {"id": "biological", "title": "Biological Treatment"}])
    else:
        fs = Flowsheet("SYNTHETIC " + key.upper())
        feed, product = fs.add(Feed("Feed")), fs.add(Product("Product"))
        if key == "parallel-pumps":
            inlet = fs.add(Junction("Suction", inputs=1, outputs=3))
            outlet = fs.add(Junction("Discharge", inputs=3, outputs=1))
            fs.connect(feed.outlet, inlet.inlets[0], name="feed")
            for index in range(3):
                pump = fs.add(Pump(f"250-P-{index+1:02}", variant="rotary_lobe"))
                fs.connect(inlet.outlets[index], pump.suction, name=f"suction-{index+1}")
                fs.connect(pump.discharge, outlet.inlets[index], name=f"discharge-{index+1}")
            fs.connect(outlet.outlets[0], product.inlet, name="product")
            fs.layout_options.parallel_trains = True
        else:
            primary = fs.add(Fitting("250-FE-01", variant="magnetic"))
            valve = fs.add(Valve("250-FCV-01", variant="butterfly_pneumatic"))
            fit = fs.add(Instrument("250-FIT-01"))
            fit.attach(primary, at="N")
            fic = fs.add(Instrument("250-FIC-01", variant="shared"))
            fs.connect(feed.outlet, primary.inlet, name="feed")
            fs.connect(primary.outlet, valve.inlet, name="measured")
            fs.connect(valve.outlet, product.inlet, name="product")
            fs.connect(fit.sig_out, fic.sig_in, kind="electric", name="measurement")
            fs.connect(fic.sig_out, valve.actuator, kind="pneumatic", name="output")
    data = fs.to_dict()
    # Do not advertise an example that the same installed engine cannot read.
    if Flowsheet.from_dict(json.loads(json.dumps(data))).to_dict() != data:
        raise ValueError("Discovery example does not round-trip")
    return {"key": key, "description": EXAMPLES[key], "synthetic": True,
            "render_options": {"jump_direction": "auto", "crossing_style": "gap"}, "spec": data}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    listing = sub.add_parser("catalog")
    listing.add_argument("--query")
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--limit", type=int, default=20)
    unit = sub.add_parser("unit")
    unit.add_argument("name")
    unit.add_argument("--variant", default="default")
    unit.add_argument("--parameters", type=json.loads, default={})
    sample = sub.add_parser("example")
    sample.add_argument("key", choices=sorted(EXAMPLES))
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    value = {"catalog": catalog, "unit": describe_unit, "example": example}[command](**args)
    print(json.dumps(value, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
