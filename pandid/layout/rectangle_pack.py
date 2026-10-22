"""Deterministic bounded packing of measured process envelopes, no scaling."""
from __future__ import annotations


def pack(rectangles, width, height, links=()):
    """Try deterministic measured shelf orders before declaring no placement.

    A single greedy short-side order can strand a narrow corridor despite
    sufficient paper. Alternatives change placement only, never dimensions.
    """
    orders = (
        lambda r: (-r[1]*r[2], str(r[0])),
        lambda r: (-r[2], -r[1], str(r[0])),
        lambda r: (-r[1], -r[2], str(r[0])),
        lambda r: (-max(r[1:]), -min(r[1:]), str(r[0])),
        lambda r: (-sum(r[1:]), str(r[0])),
    )
    candidates = []
    for order in orders:
        for mode in ('short-side', 'area', 'bottom-left', 'long-side'):
            result = _attempt(sorted(rectangles, key=order), width, height, links, mode)
            if result is not None:
                # Feasibility alone can scatter connected stations around
                # the last free corners. Compare complete arrangements so
                # relief branches and return paths stay near their hosts.
                length = sum(abs(result[a][0]+result[a][2]/2-result[b][0]-result[b][2]/2)
                             +abs(result[a][1]+result[a][3]/2-result[b][1]-result[b][3]/2)
                             for a,b in links if a in result and b in result)
                candidates.append((length,len(candidates),result))
    return min(candidates,key=lambda c:c[:2])[2] if candidates else None


def _attempt(rectangles, width, height, links, mode):
    free = [(0., 0., width, height)]
    placed = {}
    neighbours = {key: set() for key, _, _ in rectangles}
    for a, b in links:
        if a in neighbours and b in neighbours:
            neighbours[a].add(b);neighbours[b].add(a)
    for key, w, h in rectangles:
        candidates=[]
        for x,y,fw,fh in free:
            if fw < w-.01 or fh < h-.01:
                continue
            distance = sum(abs(x+w/2-(placed[p][0]+placed[p][2]/2))+
                           abs(y+h/2-(placed[p][1]+placed[p][3]/2)) for p in neighbours[key] if p in placed)
            score = {
                'short-side': (min(fw-w,fh-h), distance, max(fw-w,fh-h), y, x),
                'long-side': (max(fw-w,fh-h), distance, min(fw-w,fh-h), y, x),
                'area': (fw*fh-w*h, distance, min(fw-w,fh-h), y, x),
                'bottom-left': (y+h, x, distance, min(fw-w,fh-h)),
            }[mode]
            candidates.append((score,(x,y,w,h)))
        if not candidates:
            return None
        _, box = min(candidates)
        placed[key]=box
        px,py,pw,ph=box
        split=[]
        for x,y,fw,fh in free:
            if px>=x+fw or px+pw<=x or py>=y+fh or py+ph<=y:
                split.append((x,y,fw,fh));continue
            if px>x:split.append((x,y,px-x,fh))
            if px+pw<x+fw:split.append((px+pw,y,x+fw-px-pw,fh))
            if py>y:split.append((x,y,fw,py-y))
            if py+ph<y+fh:split.append((x,py+ph,fw,y+fh-py-ph))
        free=[a for i,a in enumerate(split) if not any(i!=j and a[0]>=b[0] and a[1]>=b[1]
              and a[0]+a[2]<=b[0]+b[2] and a[1]+a[3]<=b[1]+b[3] and (a!=b or i>j)
              for j,b in enumerate(split))]
    return placed
