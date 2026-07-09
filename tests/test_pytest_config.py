"""Contract tests for repository-wide pytest collection settings."""


def test_local_tmp_tree_is_not_collected(pytestconfig):
    assert "tmp" in pytestconfig.getini("norecursedirs")
