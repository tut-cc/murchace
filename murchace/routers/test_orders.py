import sqlparse
from inline_snapshot import snapshot

from .orders import OrderFilter, query_items, query_orders


def format_sql(sql: str):
    return sqlparse.format(sql, keyword_case="upper", reindent=True, wrap_after=80)


def test_query_items():
    filter = OrderFilter(
        card="item", statuses=["unprocessed"], allCategory=True, categories=["1", "2"]
    )
    assert format_sql(str(query_items(filter))) == snapshot(
        """\
SELECT ordered_items.order_id, ordered_items.item_no, ordered_items.product_id, ordered_items.count,
       ordered_items.supplied_at, ordered_items.id, products.name, products.filename, orders.ordered_at
FROM ordered_items
JOIN products ON products.product_id = ordered_items.product_id
JOIN orders ON orders.order_id = ordered_items.order_id
WHERE (:param_1
       OR orders.canceled_at IS NULL
       AND orders.completed_at IS NULL)
  AND :param_2
ORDER BY ordered_items.order_id ASC, ordered_items.item_no ASC, ordered_items.product_id ASC\
"""
    )
    filter.all_category = False
    assert format_sql(str(query_items(filter))) == snapshot("""\
SELECT ordered_items.order_id, ordered_items.item_no, ordered_items.product_id, ordered_items.count,
       ordered_items.supplied_at, ordered_items.id, products.name, products.filename, orders.ordered_at
FROM ordered_items
JOIN products ON products.product_id = ordered_items.product_id
JOIN orders ON orders.order_id = ordered_items.order_id
WHERE (:param_1
       OR orders.canceled_at IS NULL
       AND orders.completed_at IS NULL)
  AND products.category_id IN (__[POSTCOMPILE_category_id_1])
ORDER BY ordered_items.order_id ASC, ordered_items.item_no ASC, ordered_items.product_id ASC\
""")


def test_query_orders():
    filter = OrderFilter(
        card="order",
        statuses=["unprocessed", "completed"],
        allCategory=True,
        categories=["1", "2"],
    )
    assert format_sql(str(query_orders(filter))) == snapshot(
        """\
SELECT orders.order_id, orders.ordered_at, orders.canceled_at, orders.completed_at,
       ordered_items.item_no, ordered_items.product_id, ordered_items.count, ordered_items.supplied_at,
       products.name, products.price
FROM orders
JOIN ordered_items ON orders.order_id = ordered_items.order_id
JOIN products ON products.product_id = ordered_items.product_id
WHERE :param_1
  OR orders.canceled_at IS NULL
  AND orders.completed_at IS NULL
  OR orders.completed_at IS NOT NULL
ORDER BY orders.order_id DESC, ordered_items.id ASC, ordered_items.item_no ASC\
"""
    )
