# Circle H2O process engine extensions

This fork is the drafting engine for BFDs, PFDs and P&IDs in PuranOS. The
upstream typed units, named ports, constraint layout, A* routing and native
exporters remain the implementation. No PuranOS database or process solver
runs in this package.

`profiles.circle_h2o.block_diagram` supplies BFD house ink and wrapped block
labels. `profiles.templates.from_template` maps reviewed semantic symbols and
named port aliases to typed units; unmapped symbols and ports fail explicitly.
`profiles.legend.pages` uses the same units and streams for discipline legends.

An ordered `lanes=[{'id': ..., 'title': ...}]` argument to `block_diagram`
selects the process roll-up profile. Blocks carry `lane`, numeric `order`, and
optional logical `column`/`row`. The engine reserves explicit slots, wraps
labels, uses a common block size, and draws transparent lane bands with stable
identities. These are layout hints; source block and stream identities survive.

Use `jump_direction='auto', crossing_style='gap'` for native drawing sets.
The engine chooses a realizable edge order and gives either crossing line its
gap, preserving room for bends and terminal arrows. Fixed vertical/horizontal
hop preferences can impose contradictory drawing orders on repeated crossings.
An impossible automatic crossing clearance fails rather than emitting flat
crossings. Native-export validation must also check actual gap ink.

`Junction(inputs=..., outputs=...)` represents connected piping, with a dot for
a tee and a vertical pipe header for multiple parallel takeoffs. It has real
named ports and no triangle or visible equipment tag. Mixer and Splitter retain
their upstream process-unit meaning; the house `process.junction` mapping uses
Junction. `layout_options.parallel_trains` aligns equivalent pump/valve trains
between common headers without changing connectivity or overriding pins.
`control_grid` selects deterministic staged control placement; a zero value
retains upstream placement. The house profile uses a one-pixel grid.

`Stream.flow_class='secondary'` selects the lighter process-line weight; the
default is `main`. Medium and engineering connection identity are independent.
`Region` and `Caption` in `pandid.drawing_regions` add editable grouped panels,
lane headings and adjacent explanatory text, and round-trip through the spec.
Legends group the admitted catalogue by equipment, valves/actuators, piping,
instrumentation, line/signal media, tagging, nameplates and abbreviations. They
are one multi-sheet document per discipline, following the Nanded reference
arrangement. They do not assert that unreviewed symbols are qualified.

`Flowsheet.drawio_metadata` carries opaque source and stable appearance IDs
through serialization. draw.io user objects hold these values; cell endpoints
and child ownership follow remapped IDs. No engineering UUID is inferred from
a visible tag. `display_label` controls visible lettering independently.

`TitleBlock.logo`, `logo_aspect`, `fit_fields` and `extra_fields` preserve the
native title strip, add an embedded aspect-correct logo in the company cell,
and keep long document-control values whole. Logos accept embedded SVG/PNG/JPEG,
never remote URLs. `print_scale` enlarges native lettering and furniture before
fitting to physical paper. Both SVG and draw.io consume the same geometry.

`equipment_data` provides individual left-aligned equipment nameplates with
all tags in their heading and supplied rows below. Boxes share an above/below
horizontal; overflow expands the required bounds rather than dropping fields.
Boundary `reference_code` creates a divided flag with code, service and reference.
Its editable children belong to the boundary symbol.

An MBR flow sensor is `Fitting(tag, variant='magnetic')` and
`fs.add_balloon(element, at='N')`. The M appears in the native inline sensor;
the FIT balloon, stem and typed controller connections remain separate editable
appearances of the same instrument. Rotary-lobe pumps, membrane cages and
airlifts are original house candidates requiring engineering qualification.

Explicit `.via()` waypoints remain fixed. Terminal overlap repair can shorten
an automatic run only when it preserves endpoints, removes an overlap and
introduces no new overlap or equipment intersection. It does not fix conflicts
between manually pinned paths; the publication caller must refuse unresolved
findings. Standards-informed features are not certification of a complete sheet.

Regenerate symbols with `python scripts/vendor_symbols.py` and
`python scripts/house_symbols.py`. Regenerate examples with
`python scripts/drawio_samples.py`. Run `python -m pytest tests` in a development
installation; the focused custody/branding contract is `test_engine_extensions.py`.
