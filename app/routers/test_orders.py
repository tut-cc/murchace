import sqlparse
from inline_snapshot import snapshot

from .orders import query_incoming, query_ordered_items_incoming, query_resolved


def format_sql(sql: object):
    return sqlparse.format(sql, keyword_case="upper", reindent=True, wrap_after=80)


def test_incoming_ordered_items_query():
    assert format_sql(str(query_ordered_items_incoming)) == snapshot(
        """\
SELECT ordered_items.order_id, ordered_items.product_id, count(ordered_items.product_id) AS COUNT,
       products.name, products.filename, unixepoch(orders.ordered_at) AS ordered_at
FROM ordered_items
JOIN products ON products.product_id = ordered_items.product_id
JOIN orders ON orders.order_id = ordered_items.order_id
WHERE ordered_items.supplied_at IS NULL
  AND orders.canceled_at IS NULL
  AND orders.completed_at IS NULL
GROUP BY ordered_items.order_id, ordered_items.product_id
ORDER BY ordered_items.product_id ASC, ordered_items.order_id ASC\
"""
    )


def test_incoming_orders_query():
    assert format_sql(str(query_incoming)) == snapshot(
        """\
SELECT orders.order_id, unixepoch(orders.ordered_at) AS ordered_at, ordered_items.product_id,
       unixepoch(ordered_items.supplied_at) AS supplied_at, count(ordered_items.product_id) AS COUNT, products.name
FROM orders
JOIN ordered_items ON orders.order_id = ordered_items.order_id
JOIN products ON products.product_id = ordered_items.product_id
WHERE orders.canceled_at IS NULL
  AND orders.completed_at IS NULL
GROUP BY orders.order_id, ordered_items.product_id
ORDER BY orders.order_id ASC, ordered_items.product_id ASC\
"""
    )


def test_resolved_orders_query():
    assert format_sql(str(query_resolved)) == snapshot(
        """\
SELECT orders.order_id, unixepoch(orders.ordered_at) AS ordered_at,
       unixepoch(orders.canceled_at) AS canceled_at, unixepoch(orders.completed_at) AS completed_at, ordered_items.product_id,
       unixepoch(ordered_items.supplied_at) AS supplied_at, count(ordered_items.product_id) AS COUNT, products.name, products.price
FROM orders
JOIN ordered_items ON orders.order_id = ordered_items.order_id
JOIN products ON products.product_id = ordered_items.product_id
WHERE orders.canceled_at IS NOT NULL
  OR orders.completed_at IS NOT NULL
GROUP BY orders.order_id, ordered_items.product_id
ORDER BY orders.order_id ASC, ordered_items.product_id ASC\
"""
    )
