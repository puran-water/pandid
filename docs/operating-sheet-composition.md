# Operating sheet composition

Templates opt in with `layout-subsystem` metadata. `layout.subsystems.place` keeps complete pump and filter banks, serial process paths and held pipe interfaces together, then packs their measured equipment, instrumentation and caption footprints. `process-layout` installs the optional bounded packing solver. All symbols, engineering text and fixed printed sizes remain unchanged; an infeasible sheet still fails capacity validation.

The planner preserves one common equipment-data row. Once routed ink and captions have been measured, `render.nameplates.plan(fit_to_ink=True)` can reclaim empty paper above that row. It cannot remove data, change type size or add another row.

`routing.captions` reserves equipment lettering with the renderer's stroke clearance and one measured caption span per physical line. `Stream.label_group` associates consecutive pipe segments with that one label; it does not merge connections. Free controllers use stable nominal caption reservations, avoiding feedback from route-dependent tag placement. Final native routes, crossing gaps, labels and bodies are still checked by the ordinary export gates.

`HeldPipeEnd` depicts an unresolved engineering interface as a pipe break with an explicit inlet or outlet. It is not an equipment tag or invented vessel. Its construction parameters and physical-line label groups survive the native spec round trip.

Regression coverage: `tests/test_operating_composition.py`, `tests/test_crossing_clearance.py`, `tests/test_spec.py` and `tests/test_pressure_and_dosing_symbols.py`. The original construction artwork and public-reference licence notes are in `house-membrane-symbols.md`.
