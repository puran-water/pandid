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

    @property
    def stencil(self):
        connections = "".join(
            f'<constraint name="{name}" x="{x}" y="{y}" perimeter="0"/>' for name, x, y in self.anchors
        )
        return f'<shape name="HouseMbrCandidate" w="{self.width}" h="{self.height}" aspect="fixed" strokewidth="inherit"><connections>{connections}</connections><foreground>{self.drawing}</foreground></shape>'


ARTWORK = {
    "house.mbr.membrane_cage": HouseArtwork(
        "Submerged membrane cage; fiber strokes do not specify module count",
        90,
        120,
        30,
        40,
        (("N", 0.5, 0), ("S", 0.5, 1), ("W", 0, 0.5), ("E", 1, 0.5)),
        '<rect x="10" y="15" w="70" h="90"/><stroke/>'
        '<path><move x="45" y="0"/><line x="45" y="15"/><move x="15" y="25"/><line x="75" y="25"/></path><stroke/>'
        + "".join(
            f'<path><move x="{x}" y="25"/><line x="{x}" y="82"/><quad x1="{x + 4}" y1="102" x2="{x + 8}" y2="82"/><line x="{x + 8}" y="25"/></path><stroke/>'
            for x in (20, 34, 48, 62)
        )
        + '<path><move x="45" y="120"/><line x="45" y="105"/><move x="0" y="60"/><line x="10" y="60"/><move x="80" y="60"/><line x="90" y="60"/></path><stroke/>',
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
