# Circle H2O engine defects — 2026-09-11

Implemented on `puranos/engine-defects-20260911`, created directly from
`c72eb30235687e38bc514d6c0b8193c93cb77c2e`. No merge, rebase or push.

The final full suite reports **42 failed, 17200 passed, 726 skipped, 0 errors; exit 1**.
The suite remains red for the explicitly deferred causes below. Its failure/error
set is a subset of the established 565-entry baseline:

- **Final minus baseline: 0 entries.** No new failing/error node IDs.
- **Baseline minus final: 523 entries** (515 now passed, 8 now skipped).
- **Final minus c72eb30: 0; c72eb30 minus final: 523.**

The [565-row ledger](engine-defects-20260911.csv) names every original node ID,
its root cause, draw.io relevance and evidence, final outcome, and set membership.
The [machine-readable comparison](engine-defects-20260911.json) records exact
counts, retained IDs, evidence hashes and native-export measurements. The supplied
baseline logs were parsed, not rerun: b720dbb had 73 failed / 16601 passed /
720 skipped / 492 errors; c72eb30 had 73 / 16605 / 720 / 492, with identical
failure sets.

## What changed and why

**Routing endpoints.** The terminal micro-jog pass was copying the rendered
polyline back into route waypoints even when it made no repair. Rendered endpoints
are `port_point` nozzles, which can sit inside the equipment box; route endpoints
are `port_anchor` points on that box. Terminal-arrow and crossing-clearance repairs
made the same conflation. The micro-jog pass now works on routing waypoints, and
both other repairs preserve the route's existing endpoint anchors before saving.
This keeps clearance repair a geometry operation, without making it resolve port
objects again. Renderers still add the nozzle stubs, and manually authored routes
remain protected. All 12
previously failing route-endpoint scenarios pass. The initial 4–10 px report
identified corrupted routing state; it did not by itself prove a visible nozzle
gap, because native edges already attached to the actual `port_point`.

**Native fixed aspect and flips.** The house generator threw away the stencil's
`aspect="fixed"` attribute. Routing then stretched its port coordinates while
native draw.io kept the artwork proportional. Preserve that attribute in the
generated `Symbol`, and normalize native connection fractions against the
centered fixed-stencil rectangle used by `mxCellState.getPerimeterBounds`.
Otherwise draw.io applies the inset twice. Desktop export also exposed a
quarter-turn/single-axis-mirror defect: native shape flips use placed axes while
the model mirrors symbol axes before rotation, and `Graph.getLegacyConnectionPoint`
exchanges flip axes for north/south. `_placement` now writes the corresponding
native style keys while returning the original pair for the inverse connection
calculation. Invisible tee cells join every edge at their center, so their flip
keys have no geometric effect and retain their established serialization. No
house stencil artwork or quadratic curves were changed.

This is why the 492 setup errors are classified as relevant shared metadata,
even though their immediate `_baked` exception is SVG-only. Preserving the
fixed aspect avoids anisotropic baking in their common odd-box fixture and
clears every setup error. It does **not** implement direct quadratic-path baking;
the five direct SVG-only failures remain. Some formerly blocked cases now reach
their existing skip conditions, and one now reaches the stale airlift open-mouth
assertion; the ledger distinguishes these from passing tests.

**Shared nozzle geometry.** Gas-blower suction was at source y=35, outside the
west mouth that spans y=0..19.75. Its anchor is now the mouth midpoint, y=9.875.
The concrete and vertical Tank variants inherited vent, relief and drain ports
without artwork anchors, so they fell back to the body center. They now have
separate upper-rim/head and floor anchors, plus explicit wall bands for inlet/outlet
families. These changes live in the maintained generator and its generated
registry, which supplies both `portgeom` and native draw.io connections. Existing
ink, nozzle-face, family-band and placement assertions for these tank and blower
repairs pass without new exemptions.

**Port and spec contracts.** ConcreteBasin now declares its inlet/outlet families
as `tuple[Port, ...]`; BasinAgitator and SubmersibleMixer declare their shaft ports.
The spec writer omits the default `flow_class="main"`, retaining explicit secondary
flow class. The balloon reader forwards its accepted `area` field rather than
silently discarding it. A balloon may corroborate the element's area, including
blank area inheriting a house tag, but cannot rename only one mark of a shared
instrument identity. Rejection occurs before a balloon is added. The equipment-list
kind vocabulary now includes the three house basin/mixer kinds and Pipe Junction.

**Test contract corrections.** The old native-aspect assertion demanded that every
referenced stencil be stretchable, contrary to the actual fixed house sources.
Its replacement compares every symbol to its native source and checks fixed
aspect ratios. The connection-point test model now includes draw.io's actual
legacy flip-axis exchange, which the old model omitted. ConcreteBasin joins the
existing explicit family inventory, adding family checks. `Flowsheet.contain`
gets a real invocation in the argument-contract harness. No test was skipped,
xfail-marked, deleted or relaxed to accept a geometry error, and no golden/gallery
fixture was changed.

## Previously failing checks now passing

Every node below is verified against both the saved baseline and final JUnit
outcome. The CSV contains the complete per-node result.

| Fix | Previously failing/error test now passing |
|---|---|
| Routing anchors | `tests/test_route_invariants.py::test_route_endpoints_sit_on_their_ports[03_distillation_train]` |
| Tank nozzle inventory | `tests/test_symbol_invariants.py::test_every_holdup_variant_anchors_every_nozzle_its_class_declares[tank/concrete]` |
| Tank nozzle faces | `tests/test_symbol_invariants.py::test_a_relief_is_on_the_crown_and_a_drain_at_the_low_point[tank/vertical]` |
| Tank wall bands | `tests/test_symbol_invariants.py::test_every_family_face_declares_a_band[tank/concrete]` |
| Blower suction | `tests/test_symbol_invariants.py::test_ports_lie_on_drawn_geometry[blower/gas]` |
| Port annotations | `tests/test_port_annotations.py::test_every_port_built_is_annotated[ConcreteBasin]` |
| Stream serialization | `tests/test_serialize.py::test_to_dict_captures_topology` |
| Line-number serialization | `tests/test_line_numbers.py::test_a_schedule_round_trips_through_a_spec` |
| Balloon area | `tests/test_argument_contract.py::test_an_argument_that_is_accepted_is_capable_of_changing_something[spec:balloon:area]` |
| Equipment-list labels | `tests/test_titleblock.py::test_every_registered_kind_names_itself` |
| Containment coverage | `tests/test_argument_contract.py::test_every_public_entry_point_is_exercised_or_declared_out_of_reach` |
| Fixed-aspect fixture setup | `tests/test_symbol_invariants.py::test_ports_land_on_drawn_ink_at_any_box_shape[air_diffuser/default]` |

The 70 new regression cases cover fixed-stencil native connections on A1 PFD/P&ID
sheets across two box shapes, four rotations and four mirror states; repaired
inset nozzles versus routing anchors; generator reproducibility/aspect; and balloon
area through both API and spec entrypoints. All 70 pass. Running these and the
corrected native checks against the read-only b720dbb import yielded 74 failed,
13 passed, 1084 deselected (exit 1), demonstrating that they detect the original
implementation. The focused native/argument-contract run passed 134 tests, skipped
1, and deselected 2338 (exit 0). After the final clearance/tee adjustments, a
further focused run passed 121 tests (exit 0), including both regressions caught
by the first complete run, all 70 new cases, and the route-invariant suite.

## Triage of all 565 baseline entries

The counts below partition the original 565 entries. Final outcomes refer to those
same entries only, not newly collected regression cases. A "no" means no native
rendering defect was demonstrated. The small port-typing, default-serialization,
label-vocabulary and containment-harness repairs were still completed; other
"no" rows remain deferred for the reasons shown. The immediate SVG fixture
exception and the shared fixed-aspect metadata defect are distinguished above.

| Root cause | Baseline entries | Affects our draw.io workflow | Final outcomes | Evidence / disposition |
|---|---:|:---:|---|---|
| House generator drops fixed aspect; the SVG odd-box fixture then aborts on Q | 492 | yes | 483 passed, 1 failed, 8 skipped | All 492 errors share odd_box_sheets -> fs.to_svg -> _baked. That exception is SVG-only, but the generator discarded the fixed source aspect: native draw.io retained it while portgeom stretched its ports. Desktop 31.4.4 confirms the resulting diagonal approach. Preserving the source aspect and native connection rectangle fixes the shared cause and clears all setup errors; direct anisotropic Q baking remains SVG-only. |
| Route repair stores rendered nozzles as routing anchors | 12 | yes | 12 passed | square_micro_jogs, protect and crossing repair share routes with draw.io. port_anchor is the box boundary; port_point is the nozzle. Fix preserves both. Original 4-10 px discrepancies were not proof of visible gaps: native edges already attach to port_point. |
| New Tank variants omit optional nozzle anchors and family wall bands | 7 | yes | 7 passed | Tank(concrete/vertical) exposes vent, relief and drain, but missing artwork anchors fall back to the centre. The same registry and portgeom supply native edge constraints and family placement. |
| Gas-blower west port lies outside its drawn mouth | 2 | yes | 2 passed | vendor_data/drawio/pumps.xml Gas Blower mouth is y=0..19.75 at x=0; old suction y=35 is blank. The corrected midpoint y=9.875 is used by native constraints as well as SVG. |
| Stroke-proximity assertion does not allow the airlift open mouths | 2 | no | 2 failed | Airlift liquid_in=(22.5,60) is centred between riser walls x=17.5/27.5; discharge=(45,12) is between y=7/17. These open mouths intentionally put fluid ports off wall ink, like the existing pump/compressor exemptions. Moving a fluid port onto a wall would be wrong. |
| House basin/mixer typed port declarations are missing | 5 | no | 5 passed | Port annotations serve editors and static checkers; templates and the native writer use actual unit.ports/family attributes, which already existed. Fixed the missing Port/family declarations and explicit ConcreteBasin test inventory as a small authoring-contract repair; no runtime nozzle identity was changed. |
| Default main flow class is needlessly serialized | 3 | no | 3 passed | The three failures compare exact spec dictionaries. Both old and corrected specs render main flow identically; the reader already accepts it. Omitting the redundant default restores the established minimal writer contract, while secondary remains explicit and still controls native line weight. |
| Spec balloon area is accepted and discarded | 1 | yes | 1 passed | The reader now forwards area. add_balloon permits corroborating the element area and rejects changing only one mark of a shared instrument identity; applies to magnetic FIT assemblies. |
| House kinds have no explicit equipment-list label | 1 | no | 1 passed | The failure checks vocabulary completeness. document._describe already produced readable fallback names for the three house equipment kinds; geometry was unaffected. Added explicit labels and Pipe Junction for explicitly included schedule rows as a small catalogue repair. |
| Argument-contract harness omits Flowsheet.contain | 1 | no | 1 passed | This is coverage bookkeeping, not failed runtime containment. Added a real containment call to the harness because basin internals are part of the process workflow; no unexercised exemption was added. |
| Device generator does not classify 17 fork catalogue additions | 2 | no | 2 failed | scripts/gen_devices.py claims gate fails before generation; runtime units, spec and discovery use the registered symbols directly. No drawing is missing from the runtime catalogue. Deferred generator bookkeeping. |
| Upstream variant-owner tables and catalogue counts are stale | 2 | no | 2 failed | docs/api.md owner table lacks the 17 additions and README says 229 against 246 registered symbols. These documentation assertions do not execute the native writer. |
| Committed example/gallery SVGs drift from the pinned renderer | 19 | no | 19 failed | Six scenarios have identical pre-existing SVG byte comparisons failing across golden/example/gallery tests; version-bump normalization succeeds then hits the same stale 03 fixture. First differences are title positioning/width and page bounds. No committed fixture was regenerated. |
| Exact error-message expectation predates two supported input owners | 1 | no | 1 failed | Pump(inputs=2) is correctly rejected; the message now truthfully includes Junction and ConcreteBasin. Restoring the old owner list would make the diagnostic incomplete. |
| Optional raster preview backend svglib is absent | 1 | no | 1 failed | test_show invokes pandid SVG-to-PNG preview, not native draw.io Desktop PDF export. No package install was authorized. |
| Filled junction dot has no SVG outline stroke declaration | 2 | no | 2 failed | The marker is a solid fill, so universal stroked-symbol assertions reject it. Native drawio._shape emits its own ellipse/header with explicit strokeWidth and fill. |
| SVG baker skips anisotropic scaling of an unstroked fill | 4 | no | 4 failed | _uneven detects only declared strokes, so the SVG filled dot is not baked. Native Junction rendering uses mxGraph primitives and never calls _baked. |
| SVG baker lacks quadratic Bezier command support | 5 | no | 5 failed | The direct _baked Q tests still fail. Native uses the original `<quad>` instructions, verified through Desktop export; no _baked call occurs on that path. |
| Hard-coded tank variant list predates concrete and vertical | 1 | no | 1 failed | Registry.variants correctly lists the two supported additions after default. Removing valid variants to match the old literal would be a regression. |
| Vendored-source test vocabulary omits liquid_screen | 1 | no | 1 failed | The assertion fails in its own _VENDORED_SOURCE_WORDS mapping before checking the docstring. Runtime liquid-screen registration and native stencil resolution work. |
| Bare-pipe assertion predates the house Junction | 1 | no | 1 failed | Both tee/default and junction/default legitimately carry bare_run. House Junction must stay bare pipe for BFD/PFD/P&ID connectivity; removing that behavior would be wrong. |

## Native Desktop verification and constraints

The native probes use `circle-h2o.process-drafting/1`, `DRAWING_SCALE=0.44`,
`PRINT_SCALE=2.7`, and `fs.to_drawio(diagram="p&id", page_size="A1", border="zone")`.
The portable local Desktop executable reports **31.4.4**. No installation or relock
was performed. Desktop, rather than `fs.to_svg`, exported the inspected SVG and PDF
artifacts. After the final clearance/tee changes, the final code reproduced all
24 Desktop-verified input masters byte-for-byte (`native-final-inputs.json`).
Both baseline and corrected masters exported successfully to one-page A1 PDF (2383.92 × 1684.08 pt).

The distorted-airlift baseline approaches its nozzle diagonally from
(1732.52, 1220.31) to (1763.46, 1190.61) in the Desktop SVG. The corrected approach
is horizontal from (1732.52, 1190.61) to the same nozzle. The 16 final Desktop
rotation/mirror cases have **zero sloping segments**, with maximum nozzle-to-edge
endpoint discrepancy **0.01414 px**, consistent
with Desktop's two-decimal coordinate rounding. The unchanged quadratic artwork
is present in the exported native stencil.

A separate seven-port Desktop probe confirms the shared vendor geometry fixes.
Distances are from the pipe endpoint to the actual exported path centerline,
including sampled cubic curves (the suite's coarse helper substitutes chords for
cubics and overstates these distances). All seven corrected routes are orthogonal:

| Native port | Baseline distance to ink (px) | Corrected distance (px) |
|---|---:|---:|
| Gas-blower suction | 24.086 | 0 |
| Concrete tank vent / relief / drain | 45.380 each | 0 each |
| Vertical tank vent / relief | 51.890 each | 0.034 or less |
| Vertical tank drain | 51.890 | 0 |

The 0.034 px upper-head residual is below the drawn stroke half-width of 1.24 px;
the registry rounds source anchors to one decimal. The measurements and native
masters/exports are in `native-vendor-baseline-3144/` and
`native-vendor-current-3144/`; the curve-aware result is `measurements-curves.json`.
These are synthetic renderer probes, not issued engineering drawings.

Full-suite command (output and exit captured independently):

```sh
python3 -m pytest tests/ -q -p no:randomly \
  --junitxml=/tmp/pandid-engine-defects-evidence/full-suite.xml \
  > /tmp/pandid-engine-defects-evidence/full-suite.txt 2>&1
result=$?
printf '%s\n' "$result" > /tmp/pandid-engine-defects-evidence/full-suite.exit
exit "$result"
```

Raw evidence remains in `/tmp/pandid-engine-defects-evidence/`: `full-suite.txt`,
`full-suite.xml`, `targeted-final.txt`, `regressions-on-pin-final.txt`,
`baseline-minus-final.txt`, `final-minus-baseline.txt`, the native before/after
masters and `*-native-3144.svg/pdf`, and `native-placements-3144/measurements.json`.
The JSON comparison records their SHA-256 hashes. An earlier partial full run was
explicitly interrupted to correct the Desktop-discovered flip defect; it is
archived as `full-suite-attempt-1.*` and is not used for the final counts.
The first complete run (`full-suite-attempt-2.*`) reported 44 failed / 17198 passed /
726 skipped / 0 errors and exposed two regressions: a geometry-only clearance
fixture had no port objects, and the invisible tee's inert flip spelling changed
the distillation master. Both were corrected in code, with their original tests
and fixtures intact, before the final full run reported here.

`git diff --check` passes. Ruff could not run because it is absent from the
available Python environment; no dependency was installed. The protected process,
layout-options, SVG-renderer and boundary-test files are byte-identical to c72eb30;
`dock_items` and `fitted_band` are unchanged. All 67 committed rendering
fixtures are unchanged, and the b720dbb worktree remains clean. Existing
line endings were retained. No writes were made under `/home/hvksh/professional`,
no monorepo or environment files were changed, and no remote, database, mail,
SharePoint or MCP write operation was used.

The complete exposed MCP tool inventory contains **engineering-mcp, plant-cad-mcp,
site-fit-mcp, office-mcp, ontology-mcp, openproject-mcp, hatchet-mcp, and wiki-global**.
The catalog exposes 256 MCP tool bindings. This corrects an incomplete early
inventory statement; no MCP tools were called. The saved inventory is
`/tmp/pandid-engine-defects-evidence/mcp-inventory-final.json`.
