def test_public_api():
    import pyliveatc
    for name in pyliveatc.__all__:
        assert hasattr(pyliveatc, name), f"Missing from pyliveatc: {name}"
