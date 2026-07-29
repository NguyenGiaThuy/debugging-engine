from cache import Cache


def test_roundtrip_same_case():
    c = Cache()
    c.set("user", 1)
    assert c.get("user") == 1


def test_roundtrip_mixed_case():
    c = Cache()
    c.set("User", 42)
    assert c.get("User") == 42
    assert c.get("user") == 42
