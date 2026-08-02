from src.tools import lookup_order, normalise_order_id, rank_products


def test_normalise_order_id_accepts_common_forms() -> None:
    assert normalise_order_id("ord-102") == "ORD102"
    assert normalise_order_id("102") == "ORD102"


def test_lookup_order_accepts_email() -> None:
    match = lookup_order("priya.patel@example.com")
    assert match is not None
    assert match[0] == "ORD102"


def test_product_ranking_respects_brand_and_budget() -> None:
    matches = rank_products("Sony headphones under $500")
    assert matches
    assert matches[0]["brand"] == "Sony"
    assert matches[0]["price"] <= 500
