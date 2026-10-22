"""Bounded compound-footprint placement, without scaling engineering ink.

The optional process-layout solver is used only after the dependency-free
packers fail. Integer bounds round occupied extents outward. Parts of one
rigid assembly may overlap; parts of distinct assemblies may not.
"""
import math


def _union(rectangles, gap):
    """Disjoint integer rectangles for the exact outward-rounded ink union."""
    boxes=[(math.floor(x),math.floor(y),math.ceil(x+w)+gap,math.ceil(y+h)+gap)
           for x,y,w,h in rectangles]
    xs=sorted({edge for x0,y0,x1,y1 in boxes for edge in (x0,x1)})
    active,result={},[]
    for left,right in zip(xs,xs[1:]):
        spans=sorted((y0,y1) for x0,y0,x1,y1 in boxes if x0<right and x1>left)
        joined=[]
        for top,bottom in spans:
            if joined and top<=joined[-1][1]:
                joined[-1]=(joined[-1][0],max(bottom,joined[-1][1]))
            else:
                joined.append((top,bottom))
        for span,start in list(active.items()):
            if span not in joined:
                result.append((start,span[0],left-start,span[1]-span[0]));del active[span]
        for span in joined:
            active.setdefault(span,left)
    if xs:
        result.extend((start,top,xs[-1]-start,bottom-top) for (top,bottom),start in active.items())
    return result


def pack(shapes, width, height, *, gap=8., obstacles=(), below=()):
    try:
        from ortools.sat.python import cp_model
    except ImportError as exc:
        raise ValueError('PROCESS_LAYOUT_SOLVER_REQUIRED: install pandid[process-layout]') from exc
    model = cp_model.CpModel()
    width, height = math.floor(width), math.floor(height)
    gap = math.ceil(gap)
    occupied = sum(w*h for _,_,_,rects in shapes for x,y,w,h in _union(rects,gap))
    occupied += sum(math.ceil(w)*math.ceil(h) for x,y,w,h in obstacles)
    if occupied > width*height:
        return None
    coordinates, dimensions, parts = {}, {}, []
    for name, w, h, rectangles in shapes:
        xmax, ymax = width-math.ceil(w)-gap, height-math.ceil(h)-gap
        if min(xmax, ymax) < 0:
            return None
        x = model.new_int_var(0, xmax, name+':x')
        y = model.new_int_var(0, ymax, name+':y')
        coordinates[name], dimensions[name] = (x, y), (w, h)
        for px,py,pw,ph in _union(rectangles,gap):
            parts.append((name,x+px,y+py,pw,ph))
    for index, (x, y, w, h) in enumerate(obstacles):
        parts.append(('fixed:'+str(index), math.floor(x), math.floor(y),
                      math.ceil(x+w)-math.floor(x), math.ceil(y+h)-math.floor(y)))
    x_intervals,y_intervals=[],[]
    for name,x,y,w,h in parts:
        x_intervals.append(model.new_fixed_size_interval_var(x,w,name+':part-x'))
        y_intervals.append(model.new_fixed_size_interval_var(y,h,name+':part-y'))
    model.add_no_overlap_2d(x_intervals,y_intervals)
    for upper, lower, clearance in below:
        model.add(coordinates[lower][1] >= coordinates[upper][1]
                  + math.ceil(dimensions[upper][1]+clearance))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_deterministic_time = 15
    solver.parameters.max_time_in_seconds = 60
    status = solver.solve(model)
    if status == cp_model.UNKNOWN:
        raise ValueError('FIXED_SCALE_SEARCH_LIMIT: no feasible fixed-scale placement found within '
                         'the bounded search; this is not a proof that the A1 sheet cannot fit')
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {name: (float(solver.value(x)), float(solver.value(y)))
            for name, (x, y) in coordinates.items()}
