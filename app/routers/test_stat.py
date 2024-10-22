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
                                          WHERE date(placements.placed_at,
                                                  'localtime') = date('now',
                                                                   'localtime')) AS count_today, products.name, products.filename, products.price,
       sum(products.price) AS total_sales,
       sum(products.price) FILTER (
                                   WHERE date(placements.placed_at,
                                           'localtime') = date('now',
                                                            'localtime')) AS total_sales_today, products.no_stock
FROM placed_items
JOIN placements ON placements.placement_id = placed_items.placement_id
JOIN products ON products.product_id = placed_items.product_id
WHERE placements.canceled_at IS NULL
GROUP BY products.product_id\
"""
    )


def test_avg_service_time_query_recent():
    assert format_sql(str(AvgServiceTimeQuery.recent())) == snapshot(
        """\
SELECT avg(CASE
               WHEN ((unixepoch() - unixepoch(placements.completed_at)) / CAST(60 AS NUMERIC) < 30) THEN unixepoch(placements.completed_at) - unixepoch(placements.placed_at)
           END) AS recent
FROM placements
WHERE placements.completed_at IS NOT NULL\
"""
    )


def test_avg_service_time_query():
    assert format_sql(str(AvgServiceTimeQuery.all_and_recent())) == snapshot(
        """\
SELECT avg(unixepoch(placements.completed_at) - unixepoch(placements.placed_at)) AS "all",
       avg(CASE
               WHEN ((unixepoch() - unixepoch(placements.completed_at)) / CAST(60 AS NUMERIC) < 30) THEN unixepoch(placements.completed_at) - unixepoch(placements.placed_at)
           END) AS recent
FROM placements
WHERE placements.completed_at IS NOT NULL\
"""
    )


def test_waiting_order_count_query():
    assert format_sql(str(WAITING_ORDER_COUNT_QUERY)) == snapshot(
        """\
SELECT count(placements.placement_id) AS count_1
FROM placements
WHERE placements.completed_at IS NULL
  AND placements.canceled_at IS NULL\
"""
    )
