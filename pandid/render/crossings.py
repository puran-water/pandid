"""A native-compatible crossing order with room for gaps and terminal arrows."""
from functools import lru_cache


@lru_cache(maxsize=4096)
def _pair_constraints(apts, bpts, radius, terminal_clearance):
    """Cache immutable geometry, never stream identities or mutable route lists."""
    forced = []
    for ai, (a, b) in enumerate(zip(apts, apts[1:])):
        for bi, (c, d) in enumerate(zip(bpts, bpts[1:])):
            ah, bh = abs(a[1]-b[1]) < 1e-6, abs(c[1]-d[1]) < 1e-6
            if ah == bh:
                continue
            h, v = ((a,b),(c,d)) if ah else ((c,d),(a,b))
            x, y = v[0][0], h[0][1]
            if not (min(h[0][0],h[1][0]) < x < max(h[0][0],h[1][0]) and
                    min(v[0][1],v[1][1]) < y < max(v[0][1],v[1][1])):
                continue
            def safe(points, n, ends):
                distances = [abs(x-p[0])+abs(y-p[1]) for p in ends]
                margins = [radius+1,
                           terminal_clearance if n == len(points)-2 else radius+1]
                return all(d > margin for d, margin in zip(distances, margins))
            sa, sb = safe(apts, ai, (a,b)), safe(bpts, bi, (c,d))
            if sa != sb:
                forced.append((0,1,x,y) if sa else (1,0,x,y))
            elif not sa:
                forced.append((None,None,x,y))
    return tuple(forced)


def crossing_order(polylines, radius, terminal_clearance=18):
    keys = list(polylines)
    forced = []
    paths = {key: tuple(tuple(point) for point in points) for key, points in polylines.items()}
    for i, left in enumerate(keys):
        for right in keys[i+1:]:
            pair = (left, right)
            for source, target, x, y in _pair_constraints(paths[left], paths[right], radius, terminal_clearance):
                hopper = None if source is None else pair[source]
                crossed = None if target is None else pair[target]
                forced.append((hopper,crossed,x,y))
    return _order(keys, forced)


def _order(keys, forced):
    before = {key: set() for key in keys}
    for hopper, crossed, _, _ in forced:
        if hopper is not None:
            before[hopper].add(crossed)
    order, done = [], set()
    while len(done) < len(keys):
        ready = [key for key in keys if key not in done and before[key] <= done]
        if not ready:
            break
        order.append(ready[0]); done.add(ready[0])
    order += [key for key in keys if key not in done]
    rank = {key:i for i,key in enumerate(order)}
    lost = {(a,b,x,y) for a,b,x,y in forced if a is None or rank[a] < rank[b]}
    return order, lost


class CrossingPlan:
    """Exact crossing order after changing one path, reusing all other pairs."""
    def __init__(self, polylines, radius, terminal_clearance=18):
        self.keys = list(polylines)
        self.paths = {k: tuple(tuple(p) for p in v) for k, v in polylines.items()}
        self.radius, self.terminal_clearance = radius, terminal_clearance
        self.pairs, self.constraints = [], []
        self.affected = {k: [] for k in self.keys}
        for i, left in enumerate(self.keys):
            for right in self.keys[i+1:]:
                index = len(self.pairs)
                self.pairs.append((left, right))
                self.affected[left].append(index)
                self.affected[right].append(index)
                self.constraints.append(self._constraints(left, right, self.paths[left], self.paths[right]))

    def _constraints(self, left, right, a, b):
        pair = (left, right)
        return tuple((None if source is None else pair[source],
                      None if target is None else pair[target], x, y)
                     for source, target, x, y in
                     _pair_constraints(a, b, self.radius, self.terminal_clearance))

    def with_path(self, key, points):
        from itertools import chain
        path = tuple(tuple(p) for p in points)
        constraints = self.constraints[:]
        for index in self.affected[key]:
            left, right = self.pairs[index]
            constraints[index] = self._constraints(left, right,
                path if left == key else self.paths[left], path if right == key else self.paths[right])
        return _order(self.keys, list(chain.from_iterable(constraints)))
