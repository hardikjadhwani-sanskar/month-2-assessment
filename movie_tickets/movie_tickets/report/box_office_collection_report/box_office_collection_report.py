# movie_tickets/movie_tickets/report/box_office_collection_report/box_office_collection_report.py

import frappe
from frappe import _


def execute(filters=None):
    """
    Entry point for the Script Report.
    Returns columns, data, message, chart, and summary.
    """
    filters = filters or {}

    columns  = get_columns()
    data     = get_data(filters)
    charts   = get_charts(data, filters)
    summary  = get_summary(data)

    return columns, data, None, charts, summary


# ─────────────────────────────────────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────────────────────────────────────

def get_columns():
    return [
        {
            "fieldname": "movie_title",
            "label":     _("Movie Title"),
            "fieldtype": "Data",
            "width":     180
        },
        {
            "fieldname": "genre",
            "label":     _("Genre"),
            "fieldtype": "Link",
            "options":   "Movie Genre",
            "width":     120
        },
        {
            "fieldname": "language",
            "label":     _("Language"),
            "fieldtype": "Data",
            "width":     100
        },
        {
            "fieldname": "total_shows",
            "label":     _("Total Shows"),
            "fieldtype": "Int",
            "width":     110
        },
        {
            "fieldname": "total_bookings",
            "label":     _("Total Bookings"),
            "fieldtype": "Int",
            "width":     120
        },
        {
            "fieldname": "total_seats_sold",
            "label":     _("Total Seats Sold"),
            "fieldtype": "Int",
            "width":     130
        },
        {
            "fieldname": "total_revenue",
            "label":     _("Total Revenue"),
            "fieldtype": "Currency",
            "width":     140
        },
        {
            "fieldname": "avg_occupancy_pct",
            "label":     _("Avg Occupancy (%)"),
            "fieldtype": "Float",
            "precision": 1,
            "width":     140
        },
        {
            "fieldname": "avg_ticket_price",
            "label":     _("Avg Ticket Price"),
            "fieldtype": "Currency",
            "width":     140
        }
    ]


# ─────────────────────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────────────────────

def get_data(filters):
    """
    Main query — JOINs across Movie, Show, Ticket Booking, Booked Seat,
    and Screen for screen_type (used in chart 2).
    All filters are parameterized — no string concatenation.
    """
    conditions, params = build_conditions(filters)

    rows = frappe.db.sql(f"""
        SELECT
            m.title                                         AS movie_title,
            m.genre                                         AS genre,
            m.language                                      AS language,

            COUNT(DISTINCT s.name)                          AS total_shows,
            COUNT(DISTINCT tb.name)                         AS total_bookings,
            COALESCE(SUM(tb.number_of_seats), 0)            AS total_seats_sold,
            COALESCE(SUM(tb.total_amount), 0)               AS total_revenue,

            ROUND(
                AVG(
                    CASE
                        WHEN s.total_seats > 0
                        THEN (s.booked_seats / s.total_seats) * 100
                        ELSE 0
                    END
                ), 1
            )                                               AS avg_occupancy_pct,

            CASE
                WHEN COALESCE(SUM(tb.number_of_seats), 0) > 0
                THEN ROUND(SUM(tb.total_amount) / SUM(tb.number_of_seats), 2)
                ELSE 0
            END                                             AS avg_ticket_price,

            -- carried for chart 2 grouping (not shown as column)
            sc.screen_type                                  AS screen_type

        FROM
            `tabMovie`          m
            INNER JOIN `tabShow`           s  ON s.movie          = m.name
            INNER JOIN `tabScreen`         sc ON sc.name          = s.screen
            LEFT  JOIN `tabTicket Booking` tb ON tb.show          = s.name
                                             AND tb.booking_status NOT IN ('Cancelled', 'Expired')
                                             AND tb.docstatus      = 1

        WHERE
            {conditions}

        GROUP BY
            m.title, m.genre, m.language, sc.screen_type

        ORDER BY
            total_revenue DESC
    """, params, as_dict=True)

    # Collapse screen_type rows into one row per movie
    # (a movie can show on multiple screen types)
    return collapse_by_movie(rows)


def build_conditions(filters):
    """
    Builds a parameterized WHERE clause from the filter values.
    Always includes a base condition so WHERE is never empty.
    """
    conditions = ["s.docstatus != 2"]
    params     = {}

    if filters.get("theater"):
        conditions.append("s.theatre = %(theater)s")
        params["theater"] = filters["theater"]

    if filters.get("genre"):
        conditions.append("m.genre = %(genre)s")
        params["genre"] = filters["genre"]

    if filters.get("language"):
        conditions.append("m.language = %(language)s")
        params["language"] = filters["language"]

    if filters.get("from_date"):
        conditions.append("s.show_date >= %(from_date)s")
        params["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("s.show_date <= %(to_date)s")
        params["to_date"] = filters["to_date"]

    return " AND ".join(conditions), params


def collapse_by_movie(rows):
    """
    The SQL query groups by movie + screen_type producing multiple rows
    per movie (one per screen type). This collapses them into one row
    per movie, summing numeric values across screen types.
    The screen_type column itself is stripped — it is only used for chart 2.
    """
    movie_map = {}

    for row in rows:
        key = row.movie_title

        if key not in movie_map:
            movie_map[key] = {
                "movie_title":      row.movie_title,
                "genre":            row.genre,
                "language":         row.language,
                "total_shows":      row.total_shows      or 0,
                "total_bookings":   row.total_bookings   or 0,
                "total_seats_sold": row.total_seats_sold or 0,
                "total_revenue":    row.total_revenue    or 0,
                "avg_occupancy_pct": row.avg_occupancy_pct or 0,
                "avg_ticket_price": row.avg_ticket_price or 0,
                # keep screen_type rows for chart 2
                "_screen_type_revenues": {
                    row.screen_type: float(row.total_revenue or 0)
                }
            }
        else:
            # Sum across screen types for the same movie
            existing = movie_map[key]
            existing["total_shows"]       += row.total_shows      or 0
            existing["total_bookings"]    += row.total_bookings   or 0
            existing["total_seats_sold"]  += row.total_seats_sold or 0
            existing["total_revenue"]     += row.total_revenue    or 0

            # Avg occupancy — simple average of averages (approximation)
            existing["avg_occupancy_pct"] = round(
                (existing["avg_occupancy_pct"] + (row.avg_occupancy_pct or 0)) / 2, 1
            )

            # Recalculate avg ticket price from totals
            if existing["total_seats_sold"] > 0:
                existing["avg_ticket_price"] = round(
                    existing["total_revenue"] / existing["total_seats_sold"], 2
                )

            st = row.screen_type or "Standard"
            existing["_screen_type_revenues"][st] = (
                existing["_screen_type_revenues"].get(st, 0)
                + float(row.total_revenue or 0)
            )

    return list(movie_map.values())


# ─────────────────────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────────────────────

def get_charts(data, filters):
    """
    Returns a list of two chart definitions:
    Chart 1 — Bar: Top 10 movies by revenue
    Chart 2 — Pie: Revenue by screen type
    """
    if not data:
        return None

    # ── Chart 1: Top 10 movies by revenue (Bar) ───────────────────────────────
    top10 = sorted(data, key=lambda r: r["total_revenue"], reverse=True)[:10]

    bar_chart = {
        "data": {
            "labels":   [r["movie_title"] for r in top10],
            "datasets": [
                {
                    "name":   "Revenue (₹)",
                    "values": [round(r["total_revenue"], 2) for r in top10],
                    "chartType": "bar"
                }
            ]
        },
        "type":   "bar",
        "title":  "Top 10 Movies by Revenue",
        "colors": ["#1f77b4"],
        "axisOptions": {
            "xIsSeries": 1
        },
        "barOptions": {
            "stacked": 0
        }
    }

    # ── Chart 2: Revenue by screen type (Pie) ────────────────────────────────
    screen_type_totals = {}
    for row in data:
        for stype, rev in row.get("_screen_type_revenues", {}).items():
            label = stype or "Standard"
            screen_type_totals[label] = screen_type_totals.get(label, 0) + rev

    pie_chart = {
        "data": {
            "labels":   list(screen_type_totals.keys()),
            "datasets": [
                {
                    "name":   "Revenue by Screen Type",
                    "values": [round(v, 2) for v in screen_type_totals.values()]
                }
            ]
        },
        "type":   "pie",
        "title":  "Revenue by Screen Type",
        "colors": ["#2ca02c", "#ff7f0e", "#9467bd", "#d62728"]
    }

    return [bar_chart, pie_chart]


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY ROW (shown at bottom of report)
# ─────────────────────────────────────────────────────────────────────────────

def get_summary(data):
    """
    Returns summary KPI cards shown above the report table.
    """
    if not data:
        return []

    total_revenue    = sum(r["total_revenue"]    for r in data)
    total_bookings   = sum(r["total_bookings"]   for r in data)
    total_seats_sold = sum(r["total_seats_sold"] for r in data)
    avg_occupancy    = round(
        sum(r["avg_occupancy_pct"] for r in data) / len(data), 1
    ) if data else 0

    return [
        {
            "value":       total_revenue,
            "label":       _("Total Revenue"),
            "datatype":    "Currency",
            "indicator":   "green"
        },
        {
            "value":       total_bookings,
            "label":       _("Total Bookings"),
            "datatype":    "Int",
            "indicator":   "blue"
        },
        {
            "value":       total_seats_sold,
            "label":       _("Total Seats Sold"),
            "datatype":    "Int",
            "indicator":   "blue"
        },
        {
            "value":       avg_occupancy,
            "label":       _("Avg Occupancy (%)"),
            "datatype":    "Float",
            "indicator":   "orange"
        }
    ]