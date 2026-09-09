"""Divided continuation flags: reference code in the tail, service in the body."""
from pandid.render.svg import boundary_flag
from pandid.render.escape import escaped


def parts(unit):
    (left, top, right, bottom), depth, east = boundary_flag(unit, unit.frame)
    width, height = right - left, bottom - top
    tail = max(30, .20 * width)
    divider = left + tail if east else right - tail
    code = (left if east else divider, top, tail, height)
    text = (divider if east else left + depth, top, width - tail - depth, height)
    return (divider, top, divider, bottom), code, text


def svg(unit):
    divider, code, body = parts(unit)
    x1,y1,x2,y2=divider
    out=[f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" stroke-width="1"/>']
    for text, box, font in ((unit.reference_code, code, 15), (unit.tag, body, 12)):
        x,y,w,h=box
        lines=text.splitlines()
        for n,line in enumerate(lines):
            cy=y+h/2+(n-(len(lines)-1)/2)*14
            out.append(f'<text x="{x+w/2}" y="{cy}" font-family="sans-serif" font-size="{font}" text-anchor="middle" dominant-baseline="middle">{escaped(line)}</text>')
    return out
