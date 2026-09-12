# Circle H2O process engine extensions

This fork is the drafting engine for BFDs, PFDs and P&IDs in PuranOS. The
upstream typed units, named ports, constraint layout, A* routing and native
exporters remain the implementation. No PuranOS database or process solver
runs in this package.

`profiles.circle_h2o.block_diagram` supplies BFD house ink and wrapped block
labels. `profiles.templates.from_template` maps reviewed semantic symbols and
named port aliases to typed units; unmapped symbols and ports fail explicitly.
`profiles.legend.pages` uses the same units and streams for discipline legends.

Grouped template appearances may retain member paths from different headers.
`from_template` supplies a connected pipe fan at their shared drawing nozzle,
preserving every supplied path identity. The extra junction and stem are marked
as presentation geometry, with no equipment identity. An ordinary equipment
nozzle still refuses duplicate connections. Material and energy connections use
distinct declared vessel nozzles; the water aliases on a cooling tower select
its water ports rather than its air or makeup ports.

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
The equipment tag heading has its own `heading_font_size` (default 24 drawing
units); the data retain their independent body size. Native PDF publication
measures the final physical lettering, including the 5 mm house heading floor.
Boundary `reference_code` creates a divided flag with code, service and reference.
Its editable children belong to the boundary symbol.

An MBR flow sensor is `Fitting(tag, variant='magnetic')` and
`fs.add_balloon(element, at='N')`. The M appears in the native inline sensor;
the FIT balloon, stem and typed controller connections remain separate editable
appearances of the same instrument. Rotary-lobe pumps, membrane cages and
airlifts are original house candidates requiring engineering qualification.
`MembraneCage` revision 2 uses the crossed frame and feet in the Nanded reference;
`AirDiffuser` uses a submerged air header, risers and bubbles. Both have named
engineering ports. Their strokes do not specify module or diffuser quantities.
`python -m pandid.house_library --out <new-file>.xml` exports these same native
stencils as an importable draw.io library with reference hashes and revisions.

Explicit `.via()` waypoints remain fixed. Terminal overlap repair can shorten
an automatic run only when it preserves endpoints, removes an overlap and
introduces no new overlap or equipment intersection. It does not fix conflicts
between manually pinned paths; the publication caller must refuse unresolved
findings. Standards-informed features are not certification of a complete sheet.

Wide boundary flags reserve a clear column gap beyond their actual westward
overhang. Terminal clearance protects arrowheads only at headed destinations;
unheaded source branches can shorten to clear a neighbouring header takeoff.
After track separation, a bounded body-clearance pass can shift automatic
interior tracks away from equipment, preserving nozzles and authored waypoints.
It accepts only fewer body intersections without increasing parallel overlaps.
When the full track spacing cannot clear a narrow corridor, it can reduce that
clearance to half spacing or four drawing units. Terminal approaches follow the
actual nozzle normal, including when an earlier separation pass overshot a goal.
The template profile uses 20-unit minimum column gaps; measured label and instrument
halos still reserve their own space. Sheet capacity and native ink checks remain
the publication caller's gates.

Regenerate symbols with `python scripts/vendor_symbols.py` and
`python scripts/house_symbols.py`. Regenerate examples with
`python scripts/drawio_samples.py`. Run `python -m pytest tests` in a development
installation; the focused custody/branding contract is `test_engine_extensions.py`.

## Agent discovery

`pandid.discovery` reads the same constructor and symbol registries as the spec
loader. It returns paginated summaries, one unit's real named ports (including
parameter-dependent header ports and valve actuators), and small executable specs.
No second catalogue or MCP dependency is maintained inside the engine.

```bash
python -m pandid.discovery catalog --query magnetic
python -m pandid.discovery unit Valve --variant butterfly_pneumatic
python -m pandid.discovery unit Junction --parameters '{"inputs":1,"outputs":3}'
python -m pandid.discovery example magnetic-control-loop
```

The Python entrypoints are `catalog`, `describe_unit` and `example`. Examples
carry `synthetic: true`; constructor availability and valid routing do not qualify
an engineering design. PuranOS exposes these through its existing engineering MCP
alongside the canonical-source and template-publication workflows.

### Fixed process drafting and open basins

`profiles.templates.from_template()` applies `circle-h2o.process-drafting/1`:
all A1 process sheets use a common drawing scale, so text, instrument balloons,
reference flags and lineweights are independent of how full a sheet is. The
native title strip retains its own paper scale. Fixed-scale overflow raises
`FIXED_SCALE_CAPACITY`; callers must revise the arrangement instead of shrinking
lettering. `profiles.process.inspect_drawio()` checks repeated printed sizes and
boundary columns across a process/legend set. Legacy general Flowsheet callers
retain automatic fitting unless they explicitly select a fixed `drawing_scale`.

The process profile enables `layout_options.fill_columns`. Each band spends
its spare width between columns while inline valve/pump stations retain their
minimum spacing. The target is the band named by `boundary_page`, after flag
reaches, rail approaches and nozzle escape allowances. Absolute pins keep their
arrangement; a single column or protected station cannot be stretched to fill a
page. The generic option defaults to false.

Instruments declaring the same sensing host, tap and perpendicular offset share
a straight stem. Halo reservation includes the full stack depth; 44-unit bubbles
at offset 60 resolve to 60, 126, 192 and 258 units with replacement clearance.
Actuator and placement relations keep their own leaders. Template control
placement and routing use the 16-pass `control_passes` limit and report whether
they converge.

Template instrument rows may supply `measured_variable`, independently of the
function and loop fields. It uses `Instrument.annotate(variable=...)` and the
house upper-right quadrant convention, explicitly a departure from ISO
15519-2's quadrant-b scope for U tags. The field is optional. Measurements and
regression evidence are in [the completion report](sheet-fill-workstream-20260911.md).

The profile reserves four drawing units around unrelated instrument balloons
through `layout_options.instrument_clearance`. Route repair preserves this
clearance so a pipe cannot touch a signal terminal after track separation.
Declared connections still reach their own instrument ports. The generic layout
option defaults to zero for historical layouts.

Use `ConcreteBasin`, `MembraneCage`, `AirDiffuser`, `BasinAgitator` and
`SubmersibleMixer` as separately named units. Call `fs.contain(internal, basin)`
after adding both units. The basin encloses the declared internals; each keeps
its own identity, tag, ports and nameplate. The layout solver works on the outer
process graph, then places the internals before routing. A supply serving an
internal item may enter through that basin's open top; other basins remain
closed routing obstacles. Native validation still checks pipe/wall crossings.

A `Stream` with `representation="internal"` records bulk-fluid transfer,
dispersed air or mixing duty inside the same basin. It remains in the data spec
and as an invisible, endpoint-linked draw.io cell; it is not an external pipe.
Only explicit containment authorizes this representation. It must not acquire
pipe sizing, a line label or authored routing waypoints. Ordinary air/permeate
pipes remain normal routed streams. The typed spec round-trips `containments`,
`representation` and `drawing_scale`; the `basin-internals` discovery example
shows the API. House artwork remains a candidate catalogue, pending engineering
qualification rather than a claim of complete ISA compliance.

The fixed process profile searches 24 nearby stream-label bands (generic
default: seven) to keep long line numbers clear at the common printed size.
`layout_options.stream_label_bands` is a positive integer. The search budget
does not change typography or permit the A1 fit to shrink a crowded drawing.

The process profile also enables `layout_options.strict_label_clearance`.
Bare line numbers that cannot clear equipment and other text in those bands use
clear external paper with a leader. The planned text and leader extents are part
of the diagram bounds before fitting and before the common nameplate row is
placed. Both writers consume the same caption plan; data blocks cannot cover a
displaced line number.
