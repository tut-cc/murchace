import sqlparse
from inline_snapshot import snapshot

from .orders import query_incoming, query_placed_items_incoming, query_resolved


def format_sql(sql: object):
    return sqlparse.format(sql, keyword_case="upper", reindent=True, wrap_after=80)


def test_incoming_placed_items_query():
    assert format_sql(str(query_placed_items_incoming)) == snapshot(
        """\
SELECT placed_items.placement_id, placed_items.product_id, count(placed_items.product_id) AS COUNT,
       products.name, products.filename, unixepoch(placements.placed_at) AS placed_at
FROM placed_items
JOIN products ON products.product_id = placed_items.product_id
JOIN placements ON placements.placement_id = placed_items.placement_id
WHERE placed_items.supplied_at IS NULL
  AND placements.canceled_at IS NULL
  AND placements.completed_at IS NULL
GROUP BY placed_items.placement_id, placed_items.product_id
ORDER BY placed_items.product_id ASC, placed_items.placement_id ASC\
"""
    )


def test_incoming_placements_query():
    assert format_sql(str(query_incoming)) == snapshot(
        """\
SELECT placements.placement_id, unixepoch(placements.placed_at) AS placed_at, placed_items.product_id,
       unixepoch(placed_items.supplied_at) AS supplied_at, count(placed_items.product_id) AS COUNT, products.name
FROM placements
JOIN placed_items ON placements.placement_id = placed_items.placement_id
JOIN products ON products.product_id = placed_items.product_id
WHERE placements.canceled_at IS NULL
  AND placements.completed_at IS NULL
GROUP BY placements.placement_id, placed_items.product_id
ORDER BY placements.placement_id ASC, placed_items.product_id ASC\
"""
    )


def test_resolved_placements_query():
    assert format_sql(str(query_resolved)) == snapshot(
        """\
SELECT placements.placement_id, unixepoch(placements.placed_at) AS placed_at,
       unixepoch(placements.canceled_at) AS canceled_at, unixepoch(placements.completed_at) AS completed_at,
       placed_items.product_id, unixepoch(placed_items.supplied_at) AS supplied_at,
       count(placed_items.product_id) AS COUNT, products.name, products.price
FROM placements
JOIN placed_items ON placements.placement_id = placed_items.placement_id
JOIN products ON products.product_id = placed_items.product_id
WHERE placements.canceled_at IS NOT NULL
  OR placements.completed_at IS NOT NULL
GROUP BY placements.placement_id, placed_items.product_id
ORDER BY placements.placement_id ASC, placed_items.product_id ASC\
"""
    )
