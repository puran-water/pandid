# Circle H2O engine completion — 2026-09-11

Implemented on `puranos/sheet-fill-20260911`, based on `841e299a43ff1556f4733de11abe29daa08611b5`.

The coordinate pass formerly placed every column at its minimum gap and then
aligned the boundary rails to the page. Moving the rails did not spend any of
the spare paper on equipment. The process profile now enables
`layout_options.fill_columns`. Each band measures its width with `_lay_columns`
and solves a larger gap by bisection through that same pass. Halo demand makes
this width piecewise linear; multiplying coordinates would neither solve that
problem nor preserve stations. The minimum `column_gap` remains the lower bound.

Inline valve, fitting and reducer connections protect the column seams inside
an equipment station. A valve and its pump can occupy *different* columns, so
protecting only units that share a column is insufficient. Those seams retain
the original gap while the remaining seams grow. Absolute pins retain the
original arrangement. A band with only one core column or no unprotected seam
cannot grow under this policy. Symbol dimensions and both physical scales are
unchanged. The `boundary_page` and `align_boundaries` contracts are unchanged.

The target subtracts the actual flag reaches and the two existing 110-unit rail
approaches, plus one 25-unit nozzle escape allowance at each end. It reserves
room for routed ink beyond the equipment boxes. Full native export still
measures the final routes, labels and nameplates and raises
`FIXED_SCALE_CAPACITY` when they do not fit. There is no lettering reduction.

The attachment search formerly rotated a colliding sibling around its tap, and
`Pad.widened` reserved only the maximum of several identical single-balloon
charges. Shared sensing attachments now reserve their cumulative depth before
that maximum is taken. Sharing requires the same declared host, tap, offset and
perpendicular angle; a signal host, an instrument-hosted chain, an inline
zero-offset element, an absolute pin, or an actuator/placement relation does
not become a process-tap stack. Sensing on a valve is distinct from acting on
its actuator. Other attachments retain their angular collision search.

For 44-unit balloons, a replacement needs 6 units of clearance. The 22-unit
search lattice therefore gives centres at 60, 126, 192 and 258 units, rather
than 60, 82 and 104. The search starts from each reserved depth, so the fourth
balloon is no longer constrained by the old 236-unit maximum. The coordinate
halo walks still account for instrument-hosted chains. Both the layout and
routing control loops use `layout_options.control_passes`, which templates set
to 16; termination alone is not reported as convergence.

`profiles.templates._unit` defensively reads `row.get('measured_variable')` and
calls `Instrument.annotate(variable=...)`. Its descriptor is placed in quadrant
c, above and to the right by preference. The adjacent code comment explicitly
records the house departure from ISO 15519-2 5.1.3's quadrant-b scope for U tags.
The general quadrant-b mapping is unchanged. Older rows without the field
continue to render without a descriptor.

The registry's 17 unclaimed drawings now have explicit ownership in the device
generator. The rotary-lobe pump gets its own scheduled-equipment class; the
second check-valve body belongs to `CheckValve`, magnetic measurement to
`FlowElement`, and existing typed house families retain their base owners.
The committed module was regenerated from that generator, and both ownership
tables and their registry counts were updated. No golden or gallery drawing
was regenerated.

The universal line-weight failure is a contradictory test contract, not an
incorrect pen among the outlined symbols. `test_line_weight.py` requires a
nonempty authored-pen list for every registry entry, while
`test_drawio.py::test_the_pen_the_export_states_is_the_pen_the_library_draws_with`
explicitly requires the junction's authored-pen list to be empty and its artwork
to be a filled circle. Giving the dot a real 2-unit stroke makes the first test
pass and the second fail. That was detected by the full suite; the stroke
change was reverted. The existing filled-dot contract is preserved, both tests
are untouched, and the original universal assertion remains deferred. The
native draw.io pen check passes and verifies the nominal 2-unit equipment pen
on all 245 outlined registry entries. Resolving the contradiction requires an
agreed assertion contract for filled connection markers, not a different line
weight or a test-dependent renderer.

The airlift open-mouth analysis is correct. Its liquid inlet at (22.5, 60)
is centred between riser walls at x=17.5 and x=27.5; moving the port to a wall
would be an engineering error. Its discharge is similarly centred between the
walls. I left the three existing stroke-proximity assertions red instead of
broadening their exemption list. No existing test was edited, skipped, marked
xfail or removed. A future geometry contract could explicitly test mouth
centrelines, including their transformed port locations, instead of excluding
the entire symbol from ink tests.

The native permeation comparison retains every cell ID and every `fontSize`
value. A final replay of all 38 sheets also reproduces the after geometry and
draw.io hashes exactly. Restoring the filled-dot pen contract also reproduces
the two comparison sheets' native bytes, so their PDFs remain current.

The final complete suite reports **38 failed, 17,229 passed, 726 skipped,
0 errors, exit 1**, against **42 failed, 17,200 passed, 726 skipped, 0 errors,
exit 1** at the supplied baseline. Final minus baseline is the empty set.
Baseline minus final contains exactly these four node IDs:

- `tests/test_devices.py::test_every_registered_symbol_is_claimed_exactly_once`
- `tests/test_devices.py::test_the_committed_module_matches_the_generator`
- `tests/test_devices.py::test_the_pages_quote_the_registry_they_are_describing`
- `tests/test_devices.py::test_the_variants_table_gives_every_drawing_exactly_one_owner`

Both comparisons strip `FAILED`/`ERROR` and compare complete node IDs, retaining
parameter IDs. They do not treat an outcome-prefix change as a new failure.
The full result, log hashes and both node-ID sets are recorded in
[sheet-fill-suite-delta-20260911.json](sheet-fill-suite-delta-20260911.json).
The original 42-entry baseline was read from `/tmp/pandid-verify.txt`; it was
not rerun. Only a source archive of `841e299` was used for before measurements.
The read-only `b720dbb` worktree was not touched.

The focused checks cover native analyser labels, two/three/four-balloon stacks,
valve sensing versus actuator leaders, pins, independent folded-band gap
solutions, fixed-scale capacity refusal, registry consistency and the actual
permeation station spacing. The complete suite is the final regression gate.

| Permeation metric | Before | After |
| --- | ---: | ---: |
| Process appearances / connections | 25 / 23 | 25 / 23 |
| Equipment span / entire fitted page band | 39.29% | 73.45% |
| Symmetric shortfall to that entire band | 233.59 mm/side | 102.16 mm/side |
| Equipment span / allocatable core band | 52.05% | 97.29% |
| Symmetric shortfall inside the core band | 139.29 mm/side | 7.86 mm/side |
| Each pump's adjacent inlet/outlet valve gap | 20 drawing units | 20 drawing units |
| Same gap in native draw.io coordinates | 24.75 | 24.75 |
| PDF text words | 329 | 329 |

The entire fitted band is 2448.3019 drawing units, or 769.5625 mm. The two
190-unit flags and two 110-unit approaches leave a core band of 1848.3019
units, or 580.9675 mm. The raw 102.16 mm figure is **not** a claim of a 25 mm
margin to the page band: the unchanged boundary contract itself reserves
94.30 mm per side before the equipment may begin. Within the paper actually
available to the core, the 25 mm objective is met. Shortfall in this table is
half the unused width, not a claim that an asymmetric layout has equal actual
left and right margins. Equipment span excludes boundary flags, instrumentation
and the long boundary run-ins.

The source is the saved 2026-09-10 house library's 250 Membrane Bioreactor —
Permeation P&ID, including its three pump trains, labels, nameplates, flags and
title strip. Its projected engine input is committed as
`tests/fixtures/house_permeation.json`; it is input to regression checks, not a
replacement golden output. All 38 saved sheets were projected through the
existing read-only shared adapter and then rendered through `fs.to_drawio`,
with A1, zone borders, drawing scale 0.44 and print scale 2.7. No database,
publication or MCP write was involved.

All 38 sheets converge before and after. All seven pairs with identical
attachments change from a model-centre divergence of dx=51.9615, dy=30 to dx=0,
dy=66. The old native-coordinate divergence is dx=64.3024, dy=37.125, matching
the reported defect. The same 37 sheets export in both runs. The combined MBR
PFD remains over capacity in both; its required height increases when the full
stack space is reserved, and it continues to fail explicitly.

Desktop 31.4.4 exported the before and after permeation and stem comparisons.
Both permeation PDFs retain the same 329-word multiset. Word rectangles,
allowing for line labels rotating from vertical to horizontal, differ by at
most 0.0000011 point in either dimension. This checks retained print sizes,
not a new standards qualification. Runtime hashes, source hashes, per-sheet
measurements and PDF hashes are in
[sheet-fill-measurements-20260911.json](sheet-fill-measurements-20260911.json).
The local review files are under `/tmp/pandid-measures/`:
`permeation-before.pdf`, `permeation-after.pdf`, `stems-before.pdf` and
`stems-after.pdf`, with their editable `.drawio` sources.

These house layout limits remain explicit:

| Case | Remaining constraint |
| --- | --- |
| Headworks screening PFD | One core column; there is no inter-column gap to grow. |
| Membrane fine-screening PFD | One core column; there is no inter-column gap to grow. |
| Degassing-air P&ID | One core column; growing its symbol is outside the fixed-size policy. |
| Sludge separation P&ID | One protected station; filling the page would change its internal spacing. |
| Combined MBR PFD | Existing `FIXED_SCALE_CAPACITY` remains; the template needs another arrangement. |

Each remaining suite failure has its own entry in
[sheet-fill-deferred-20260911.csv](sheet-fill-deferred-20260911.csv).
