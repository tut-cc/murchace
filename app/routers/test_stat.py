import sqlparse
from inline_snapshot import snapshot

from .stat import AvgServiceTimeQuery, WAITING_ORDER_COUNT_QUERY, TOTAL_SALES_QUERY


def format_sql(sql: object):
    return sqlparse.format(sql, keyword_case="upper", reindent=True, wrap_after=80)


def test_total_sales_query():
    assert format_sql(str(TOTAL_SALES_QUERY)) == snapshot(
        """\
SELECT products.product_id, count(products.product_id) AS COUNT,
       count(products.product_id) FILTER (
                                          WHERE date(orders.ordered_at,
                                                  'localtime') = date('now',
                                                                   'localtime')) AS count_today, products.name, products.filename, products.price,
       sum(products.price) AS total_sales,
       sum(products.price) FILTER (
                                   WHERE date(orders.ordered_at,
                                           'localtime') = date('now',
                                                            'localtime')) AS total_sales_today, products.no_stock
FROM ordered_items
JOIN orders ON orders.order_id = ordered_items.order_id
JOIN products ON products.product_id = ordered_items.product_id
WHERE orders.canceled_at IS NULL
GROUP BY products.product_id\
"""
    )


def test_avg_service_time_query_recent():
    assert format_sql(str(AvgServiceTimeQuery.recent())) == snapshot(
        """\
SELECT avg(CASE
               WHEN ((unixepoch() - unixepoch(orders.completed_at)) / CAST(60 AS NUMERIC) < 30) THEN unixepoch(orders.completed_at) - unixepoch(orders.ordered_at)
           END) AS recent
FROM orders
WHERE orders.completed_at IS NOT NULL\
"""
    )


def test_avg_service_time_query():
    assert format_sql(str(AvgServiceTimeQuery.all_and_recent())) == snapshot(
        """\
SELECT avg(unixepoch(orders.completed_at) - unixepoch(orders.ordered_at)) AS "all",
       avg(CASE
               WHEN ((unixepoch() - unixepoch(orders.completed_at)) / CAST(60 AS NUMERIC) < 30) THEN unixepoch(orders.completed_at) - unixepoch(orders.ordered_at)
           END) AS recent
FROM orders
WHERE orders.completed_at IS NOT NULL\
"""
    )


def test_waiting_order_count_query():
    assert format_sql(str(WAITING_ORDER_COUNT_QUERY)) == snapshot(
        """\
SELECT count(orders.order_id) AS count_1
FROM orders
WHERE orders.completed_at IS NULL
  AND orders.canceled_at IS NULL\
"""
    )
