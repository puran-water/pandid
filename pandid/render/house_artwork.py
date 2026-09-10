"""Original native mxGraph stencil candidates for source-required MBR equipment.

These are schematic depictions, not vendor geometry or an ISA-certified catalog.
Fiber strokes and rotor lobes do not specify equipment quantities or rotor design.
Named anchors locate appearances; a template binds actual source-backed ports.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HouseArtwork:
    meaning: str
    width: float
    height: float
    minimum_width_mm: float
    minimum_height_mm: float
    anchors: tuple[tuple[str, float, float], ...]
    drawing: str
    aspect: str = "fixed"
    version: str = "1"
    reference_document: str = ""
    reference_sha256: str = ""
    reference_pages: tuple[int, ...] = ()

    @property
    def stencil(self):
        connections = "".join(
            f'<constraint name="{name}" x="{x}" y="{y}" perimeter="0"/>' for name, x, y in self.anchors
        )
        return f'<shape name="HouseProcessCandidate" w="{self.width}" h="{self.height}" aspect="{self.aspect}" strokewidth="inherit"><connections>{connections}</connections><foreground>{self.drawing}</foreground></shape>'


ARTWORK = {
    "house.mbr.membrane_cage": HouseArtwork(
        "Submerged membrane cage; crossed frame and feet follow Nanded, no module count implied",
        90,
        120,
        30,
        40,
        (("N", 0.5, 0), ("S", 0.5, 1), ("W", 0, 0.5), ("E", 1, 0.5)),
        '<rect x="10" y="15" w="70" h="83"/><stroke/>'
        '<path><move x="10" y="15"/><line x="80" y="98"/><move x="80" y="15"/><line x="10" y="98"/>'
        '<move x="45" y="0"/><line x="45" y="15"/>'
        '<move x="0" y="60"/><line x="10" y="60"/><move x="80" y="60"/><line x="90" y="60"/>'
        '<move x="18" y="98"/><line x="18" y="110"/><move x="72" y="98"/><line x="72" y="110"/>'
        '<move x="12" y="110"/><line x="24" y="110"/><move x="66" y="110"/><line x="78" y="110"/>'
        '<move x="45" y="120"/><line x="45" y="104"/><move x="27" y="104"/><line x="63" y="104"/></path><stroke/>',
        version="2",
        reference_document="Nanded 20000-1-1001 r6.pdf",
        reference_sha256="353c4e188f02b79423a1d59c53a93dd1cfa29b18b5e8e28938610dda2fb919be",
        reference_pages=(10, 11, 12),
    ),
    "house.air.diffuser_grid": HouseArtwork(
        "Submerged air diffuser grid; header, risers and bubbles, no diffuser count or rating implied",
        120, 60, 40, 20,
        (("W", 0, 0.8), ("E", 1, 0.8)),
        '<path><move x="0" y="48"/><line x="120" y="48"/></path><stroke/>'
        + "".join(
            f'<path><move x="{x}" y="48"/><line x="{x}" y="36"/>'
            f'<move x="{x-8}" y="36"/><line x="{x+8}" y="36"/></path><stroke/>'
            f'<ellipse x="{x-6}" y="23" w="3" h="3"/><stroke/>'
            f'<ellipse x="{x+3}" y="13" w="3" h="3"/><stroke/>'
            for x in (18, 39, 60, 81, 102)
        ),
        reference_document="Nanded 20000-1-1001 r6.pdf",
        reference_sha256="353c4e188f02b79423a1d59c53a93dd1cfa29b18b5e8e28938610dda2fb919be",
        reference_pages=(8, 9),
    ),
    "house.pump.rotary_lobe": HouseArtwork(
        "Rotary-lobe pump; schematic rotors, no vendor geometry claim",
        120,
        80,
        36,
        24,
        (("W", 0, 0.5), ("E", 1, 0.5)),
        '<roundrect x="15" y="5" w="90" h="70" arcsize="30"/><stroke/>'
        '<path><move x="0" y="40"/><line x="15" y="40"/><move x="105" y="40"/><line x="120" y="40"/></path><stroke/>'
        '<path><move x="42" y="12"/><curve x1="17" y1="12" x2="21" y2="34" x3="33" y3="40"/><curve x1="21" y1="46" x2="17" y2="68" x3="42" y3="68"/><curve x1="67" y1="68" x2="63" y2="46" x3="51" y3="40"/><curve x1="63" y1="34" x2="67" y2="12" x3="42" y3="12"/><close/></path><stroke/>'
        '<path><move x="78" y="12"/><curve x1="53" y1="12" x2="57" y2="34" x3="69" y3="40"/><curve x1="57" y1="46" x2="53" y2="68" x3="78" y3="68"/><curve x1="103" y1="68" x2="99" y2="46" x3="87" y3="40"/><curve x1="99" y1="34" x2="103" y2="12" x3="78" y3="12"/><close/></path><stroke/>'
        '<ellipse x="40" y="38" w="4" h="4"/><fillstroke/><ellipse x="76" y="38" w="4" h="4"/><fillstroke/>',
    ),
    "house.mbr.airlift": HouseArtwork(
        "Airlift recycle device; liquid riser and separate air injection",
        90,
        120,
        30,
        40,
        (("S", 0.5, 1), ("W", 0, 0.7), ("E", 1, 0.2)),
        '<path><move x="35" y="120"/><line x="35" y="34"/><quad x1="35" y1="14" x2="55" y2="14"/><line x="90" y="14"/><move x="55" y="120"/><line x="55" y="40"/><quad x1="55" y1="34" x2="61" y2="34"/><line x="90" y="34"/><move x="0" y="84"/><line x="41" y="84"/></path><stroke/>'
        '<ellipse x="43" y="73" w="4" h="4"/><stroke/><ellipse x="41" y="59" w="5" h="5"/><stroke/><ellipse x="45" y="44" w="4" h="4"/><stroke/>',
    ),
}


ARTWORK.update({
    "house.basin.concrete": HouseArtwork(
        "Open concrete process basin; enclosed equipment is declared separately, depth is schematic",
        400, 300, 80, 60,
        (("W", 0, .2), ("E", 1, .2)),
        '<path><move x="0" y="0"/><line x="0" y="300"/><line x="400" y="300"/><line x="400" y="0"/>'
        '<move x="6" y="0"/><line x="6" y="294"/><line x="394" y="294"/><line x="394" y="0"/></path><stroke/>'
        '<path><move x="40" y="34"/><line x="72" y="34"/><move x="45" y="39"/><line x="67" y="39"/>'
        '<move x="51" y="44"/><line x="61" y="44"/></path><stroke/>',
        aspect="variable", reference_document="Nanded 20000-1-1001 r6.pdf",
        reference_sha256="353c4e188f02b79423a1d59c53a93dd1cfa29b18b5e8e28938610dda2fb919be",
        reference_pages=(8, 9, 10, 11, 12)),
    "house.mixer.agitator": HouseArtwork(
        "Motor, vertical shaft and impeller of a basin agitator; separate equipment identity",
        64, 180, 16, 45, (("S", .5, 1),),
        '<ellipse x="17" y="0" w="30" h="30"/><stroke/>'
        '<path><move x="22" y="22"/><line x="22" y="8"/><line x="32" y="20"/><line x="42" y="8"/>'
        '<line x="42" y="22"/><move x="32" y="30"/><line x="32" y="180"/>'
        '<move x="5" y="139"/><line x="59" y="155"/><line x="59" y="163"/><line x="5" y="147"/><close/>'
        '</path><stroke/>', reference_document="Nanded 20000-1-1001 r6.pdf",
        reference_sha256="353c4e188f02b79423a1d59c53a93dd1cfa29b18b5e8e28938610dda2fb919be",
        reference_pages=(6,)),
    "house.mixer.submersible": HouseArtwork(
        "Submersible basin mixer with motor and propeller; rotation and rating remain engineering data",
        100, 70, 30, 21, (("E", 1, .5),),
        '<rect x="0" y="22" w="36" h="26"/><stroke/>'
        '<path><move x="36" y="35"/><line x="100" y="35"/></path><stroke/>'
        '<ellipse x="70" y="1" w="14" h="34"/><stroke/>'
        '<ellipse x="70" y="35" w="14" h="34"/><stroke/>',
        reference_document="Nanded 20000-1-1001 r6.pdf",
        reference_sha256="353c4e188f02b79423a1d59c53a93dd1cfa29b18b5e8e28938610dda2fb919be",
        reference_pages=(8, 9)),
})
