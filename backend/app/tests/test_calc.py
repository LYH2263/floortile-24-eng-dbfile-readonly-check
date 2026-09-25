from app.engines.tile_math import tile_count


def test_corridor_strip():
    r = tile_count(8.0, 1.2, 0.8, 0.8, 8.0)
    assert r["raw_count"] == 15
    assert r["order_count"] == 17
