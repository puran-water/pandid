# Pressure membranes and injection quills

Owner instruction: H. Kshetry, 2026-09-21. These are original house schematic
candidates in the controlled bounded catalog. Named engineering review of the
exact artwork and its template use remains required. Software and export checks
do not supply that review.

ISA's [ISA5.1 scope and publication list](https://www.isa.org/standards-and-publications/isa-standards/isa-standards-committees/isa5-1)
was consulted for instrumentation and control notation. It supplies no claimed
quill or pressure-membrane equipment outline here. Existing instrument bubbles,
line conventions and the seven existing house symbols remain unchanged.

Physical meaning and topology references, downloaded 2026-09-21:

* [SAF-T-FLO IQ Series, 2018-06](https://www.saftflo.com/_files/ugd/9142fa_8f67f70a918c4e03975bb16be63f7e82.pdf),
  page 1, SHA-256 `0640a8dc91a27f49a8b7bcc757ac30f406ee87fc66627b2ddb4dadd4519c0604`.
  The quill drawing abstracts its insertion lance and open end. The reference's
  integral check valve is deliberately separate engineering hardware in our
  candidate; procurement type, insertion length and materials remain unsupplied.
* [DuPont FilmTec Technical Manual, Rev.20, August 2026](https://www.dupont.com/content/dam/water/amer/us/en/water/public/documents/en/RO-NF-FilmTec-Manual-45-D01504-en.pdf.),
  pages 81–83 (single module, parallel and staged systems), 106 (pressure vessels),
  SHA-256 `eb7c8d7f7829e2652fa26896b53618c82cd7d05037f759a3a1c9b647f681fa97`.
  Feed, concentrate and permeate remain separate ports. Array strokes carry no
  vessel/element count or stage arrangement. Submerged MBR cages are unrelated.

`house.dosing.injection_quill` uses `InjectionQuill.chemical_in/injection`.
`house.membrane.pressure_vessel` and `house.membrane.pressure_array` use
`PressureMembrane` and `PressureMembraneArray`, with `inlet/concentrate/permeate`.
The 36 × 18, 54 × 24 and 54 × 36 mm minima respectively are house readability
judgements, not code thresholds. Inherited strokes, fixed aspects and named
anchors use the same native mxGraph converter as the existing house artwork.

Author artwork in `render/house_artwork.py`, the typed class in `units.py`, and
its `KINDS` entry in `scripts/house_symbols.py`; run the generator. The generated
`HOUSE_SYMBOL_TYPES` mapping also admits new keys to the template adapter, avoiding
a fourth hand-maintained alias list. Existing symbol records and versions do not
move. IonExchanger selection now resolves the device subclass rather than the
two-port generic Filter; its four named ports are retained.
