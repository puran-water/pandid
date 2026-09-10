from pandid.render.crossings import crossing_order


def test_reused_geometry_preserves_the_current_stream_identities():
    paths = {'a': [(0, 0), (100, 0)], 'b': [(50, -2), (50, 100)]}
    assert crossing_order(paths, 5) == (['b', 'a'], set())
    renamed = {'new-a': paths['a'], 'new-b': paths['b']}
    assert crossing_order(renamed, 5) == (['new-b', 'new-a'], set())


def test_mutating_a_route_recalculates_its_crossing_clearance():
    paths = {'a': [[0, 0], [100, 0]], 'b': [[50, -2], [50, 100]]}
    assert crossing_order(paths, 5)[0] == ['b', 'a']
    paths['b'][0][1] = -100
    assert crossing_order(paths, 5) == (['a', 'b'], set())
    paths['a'][0][0], paths['b'][0][1] = 48, -2
    assert crossing_order(paths, 5)[1] == {(None, None, 50, 0)}
