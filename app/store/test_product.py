from .product import Product
from inline_snapshot import snapshot


def test_to_price_str() -> None:
    assert Product.to_price_str(0) == snapshot("¥0")
    assert Product.to_price_str(1) == snapshot("¥1")
    assert Product.to_price_str(10) == snapshot("¥10")
    assert Product.to_price_str(100) == snapshot("¥100")
    assert Product.to_price_str(1000) == snapshot("¥1,000")
    assert Product.to_price_str(10000) == snapshot("¥10,000")
    assert Product.to_price_str(100000) == snapshot("¥100,000")
    assert Product.to_price_str(1000000) == snapshot("¥1,000,000")
    assert Product.to_price_str(10000000) == snapshot("¥10,000,000")
    assert Product.to_price_str(100000000) == snapshot("¥100,000,000")
    assert Product.to_price_str(1000000000) == snapshot("¥1,000,000,000")
