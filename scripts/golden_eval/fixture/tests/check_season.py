from simsim.season import standings


def test_standings_sorts_by_points_then_name() -> None:
    assert standings({"b": 3, "a": 3, "c": 9}) == [("c", 9), ("a", 3), ("b", 3)]
