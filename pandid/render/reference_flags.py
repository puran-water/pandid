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
    description = '\n'.join(getattr(unit, 'reference_body_lines', unit.tag.splitlines()))
    for text, box, font in ((unit.reference_code, code, getattr(unit, 'font_size', 15)), (description, body, getattr(unit, 'font_size', 12))):
        x,y,w,h=box
        lines=text.splitlines()
        for n,line in enumerate(lines):
            cy=y+h/2+(n-(len(lines)-1)/2)*font*1.2
            out.append(f'<text x="{x+w/2}" y="{cy}" font-family="sans-serif" font-size="{font}" text-anchor="middle" dominant-baseline="middle">{escaped(line)}</text>')
    return out


def wrap_reference(text, width, font):
    """Wrap controlled paths at slashes without altering any character."""
    import re
    from pandid.render.furniture import text_width
    result=[]
    for paragraph in text.splitlines() or ['']:
        line, space = '', ''
        for part in re.findall(r'[^/\s]+/?|/', paragraph):
            # A slash continues the same identifier; ordinary words keep one
            # space. Wrapping is presentation only, not a shortened reference.
            separator = '' if not line or line.endswith('/') else ' '
            trial = line + separator + part
            if line and text_width(trial,font)>width:
                result.append(line);line=part
            else:
                line=trial
            if text_width(line,font)>width:
                raise ValueError('REFERENCE_FLAG_TOKEN_CAPACITY: '+line)
        result.append(line)
    return result
