import sqlalchemy
from inline_snapshot import snapshot

from . import PlacementsQuery


def strip_lines(query: sqlalchemy.Select) -> str:
    stripped_lines = [line.strip() for line in str(query).split("\n")]
    return "\n".join(stripped_lines)


def test_incoming_placements_query():
    assert strip_lines(PlacementsQuery.incoming.placements()) == snapshot(
        """\
SELECT placements.placement_id, unixepoch(placements.placed_at) AS placed_at, placed_items.product_id, unixepoch(placed_items.supplied_at) AS supplied_at, count(placed_items.product_id) AS count, products.name
FROM placements JOIN placed_items ON placements.placement_id = placed_items.placement_id JOIN products ON products.product_id = placed_items.product_id
WHERE placements.canceled_at IS NULL AND placements.completed_at IS NULL GROUP BY placements.placement_id, placed_items.product_id ORDER BY placements.placement_id ASC, placed_items.product_id ASC\
"""
    )


def test_resolved_placements_query():
    assert strip_lines(PlacementsQuery.resolved.placements()) == snapshot(
        """\
SELECT placements.placement_id, unixepoch(placements.placed_at) AS placed_at, unixepoch(placements.canceled_at) AS canceled_at, unixepoch(placements.completed_at) AS completed_at, placed_items.product_id, unixepoch(placed_items.supplied_at) AS supplied_at, count(placed_items.product_id) AS count, products.name, products.price
FROM placements JOIN placed_items ON placements.placement_id = placed_items.placement_id JOIN products ON products.product_id = placed_items.product_id
WHERE placements.canceled_at IS NOT NULL OR placements.completed_at IS NOT NULL GROUP BY placements.placement_id, placed_items.product_id ORDER BY placements.placement_id ASC, placed_items.product_id ASC\
"""
    )
