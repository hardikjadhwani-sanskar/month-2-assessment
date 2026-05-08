import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data    = get_data(filters)
    chart   = get_chart(data, filters)
    summary = get_summary(data)
    return columns, data, None, chart, summary


# ─────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────
def get_columns():
    return [
        {
            "label":     _("Movie Title"),
            "fieldname": "movie_title",
            "fieldtype": "Data",
            "width":     200,
        },
        {
            "label":     _("Genre"),
            "fieldname": "genre",
            "fieldtype": "Link",
            "options":   "Movie Genre",
            "width":     120,
        },
        {
            "label":     _("Language"),
            "fieldname": "language",
            "fieldtype": "Data",
            "width":     100,
        },
        {
            "label":     _("Total Shows"),
            "fieldname": "total_shows",
            "fieldtype": "Int",
            "width":     110,
        },
        {
            "label":     _("Total Bookings"),
            "fieldname": "total_bookings",
            "fieldtype": "Int",
            "width":     120,
        },
        {
            "label":     _("Total Seats Sold"),
            "fieldname": "total_seats_sold",
            "fieldtype": "Int",
            "width":     130,
        },
        {
            "label":     _("Total Revenue"),
            "fieldname": "total_revenue",
            "fieldtype": "Currency",
            "width":     140,
        },
        {
            "label":     _("Avg Occupancy (%)"),
            "fieldname": "avg_occupancy",
            "fieldtype": "Float",
            "precision": 2,
            "width":     140,
        },
        {
            "label":     _("Avg Ticket Price"),
            "fieldname": "avg_ticket_price",
            "fieldtype": "Currency",
            "width":     140,
        },
    ]


# ─────────────────────────────────────────────
# DATA  (main query)
# ─────────────────────────────────────────────
def get_data(filters):
    conditions, values = build_conditions(filters)

    # Use a subquery to avoid JOIN multiplication
    # on total_seats when counting occupancy
    sql = """
        SELECT
            m.name                                              AS movie,
            m.title                                             AS movie_title,
            m.genre                                             AS genre,
            m.language                                          AS language,

            COUNT(DISTINCT s.name)                              AS total_shows,
            COUNT(DISTINCT tb.name)                             AS total_bookings,
            COUNT(bs.name)                                      AS total_seats_sold,
            COALESCE(SUM(bs.seat_price), 0)                     AS total_revenue,

            ROUND(
                CASE
                    WHEN COALESCE(seat_totals.total_capacity, 0) > 0
                    THEN (COUNT(bs.name) / seat_totals.total_capacity) * 100
                    ELSE 0
                END, 2
            )                                                   AS avg_occupancy,

            ROUND(
                CASE
                    WHEN COUNT(bs.name) > 0
                    THEN COALESCE(SUM(bs.seat_price), 0) / COUNT(bs.name)
                    ELSE 0
                END, 2
            )                                                   AS avg_ticket_price

        FROM `tabShow` s

        INNER JOIN `tabMovie` m
            ON m.name = s.movie

        INNER JOIN `tabTicket Booking` tb
            ON tb.show          = s.name
            AND tb.docstatus    = 1
            AND tb.booking_status IN ('Confirmed', 'Pending')

        INNER JOIN `tabBooked Seat` bs
            ON bs.parent = tb.name

        -- Subquery: get correct total capacity per movie (avoids multiplication)
        LEFT JOIN (
            SELECT
                s2.movie,
                SUM(s2.total_seats) AS total_capacity
            FROM `tabShow` s2
            WHERE s2.docstatus = 1
            GROUP BY s2.movie
        ) AS seat_totals
            ON seat_totals.movie = m.name

        WHERE s.docstatus = 1
        {conditions}

        GROUP BY
            m.name,
            m.title,
            m.genre,
            m.language,
            seat_totals.total_capacity

        ORDER BY total_revenue DESC
    """.format(conditions=conditions)

    rows = frappe.db.sql(sql, values, as_dict=True)

    for r in rows:
        r["avg_occupancy"]    = round(float(r.get("avg_occupancy")    or 0), 2)
        r["avg_ticket_price"] = round(float(r.get("avg_ticket_price") or 0), 2)
        r["total_revenue"]    = float(r.get("total_revenue") or 0)
        r["total_seats_sold"] = int(r.get("total_seats_sold") or 0)
        r["total_bookings"]   = int(r.get("total_bookings")   or 0)
        r["total_shows"]      = int(r.get("total_shows")      or 0)

    return rows


# ─────────────────────────────────────────────
# FILTER CONDITIONS
# ─────────────────────────────────────────────
def build_conditions(filters):
    conditions = []
    values     = {}

    if filters.get("theatre"):
        conditions.append("AND s.theatre = %(theatre)s")
        values["theatre"] = filters["theatre"]

    if filters.get("from_date"):
        conditions.append("AND s.show_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("AND s.show_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("genre"):
        conditions.append("AND m.genre = %(genre)s")
        values["genre"] = filters["genre"]

    if filters.get("language"):
        conditions.append("AND m.language = %(language)s")
        values["language"] = filters["language"]

    return " ".join(conditions), values


# ─────────────────────────────────────────────
# CHART — Bar: Top 10 movies by revenue
# (Frappe reports only support ONE native chart)
# Pie chart is rendered separately via JS
# ─────────────────────────────────────────────
def get_chart(data, filters):
    if not data:
        return None

    top10      = sorted(data, key=lambda r: r["total_revenue"], reverse=True)[:10]
    bar_labels = [r["movie_title"] for r in top10]
    bar_values = [r["total_revenue"] for r in top10]

    return {
        "data": {
            "labels":   bar_labels,
            "datasets": [
                {
                    "name":   "Total Revenue (₹)",
                    "values": bar_values,
                }
            ],
        },
        "type":        "bar",
        "colors":      ["#e8b84b"],
        "title":       "Top 10 Movies by Revenue",
        "axisOptions": {"xIsSeries": 1},
        "barOptions":  {"stacked": 0},
    }


# ─────────────────────────────────────────────
# PIE CHART DATA — Revenue by screen type
# Called by JS via whitelisted method
# ─────────────────────────────────────────────
def get_pie_chart_data(filters):
    conditions, values = build_conditions(filters)

    sql = """
        SELECT
            COALESCE(NULLIF(sc.screen_type, ''), 'Standard') AS screen_type,
            COALESCE(SUM(bs.seat_price), 0)                  AS revenue

        FROM `tabShow` s

        INNER JOIN `tabScreen` sc
            ON sc.name = s.screen

        INNER JOIN `tabMovie` m
            ON m.name = s.movie

        INNER JOIN `tabTicket Booking` tb
            ON tb.show             = s.name
            AND tb.docstatus       = 1
            AND tb.booking_status  IN ('Confirmed', 'Pending')

        INNER JOIN `tabBooked Seat` bs
            ON bs.parent = tb.name

        WHERE s.docstatus = 1
        {conditions}

        GROUP BY sc.screen_type
        ORDER BY revenue DESC
    """.format(conditions=conditions)

    return frappe.db.sql(sql, values, as_dict=True)


# ─────────────────────────────────────────────
# SUMMARY CARDS
# ─────────────────────────────────────────────
def get_summary(data):
    if not data:
        return []

    total_revenue    = sum(r["total_revenue"]    for r in data)
    total_seats_sold = sum(r["total_seats_sold"] for r in data)
    total_bookings   = sum(r["total_bookings"]   for r in data)
    total_shows      = sum(r["total_shows"]      for r in data)
    avg_occupancy    = round(
        sum(r["avg_occupancy"] for r in data) / len(data), 2
    )

    return [
        {
            "label":    _("Total Revenue"),
            "value":    total_revenue,
            "datatype": "Currency",
            "currency": frappe.defaults.get_global_default("currency") or "INR",
            "color":    "green",
        },
        {
            "label":    _("Total Seats Sold"),
            "value":    total_seats_sold,
            "datatype": "Int",
            "color":    "blue",
        },
        {
            "label":    _("Total Bookings"),
            "value":    total_bookings,
            "datatype": "Int",
            "color":    "blue",
        },
        {
            "label":    _("Total Shows"),
            "value":    total_shows,
            "datatype": "Int",
            "color":    "orange",
        },
        {
            "label":    _("Avg Occupancy (%)"),
            "value":    avg_occupancy,
            "datatype": "Float",
            "color":    "orange",
        },
    ]


# ─────────────────────────────────────────────
# WHITELISTED — called by JS for pie chart
# ─────────────────────────────────────────────
@frappe.whitelist()
def get_pie_chart_ajax(filters=None):
    import json
    f = json.loads(filters) if isinstance(filters, str) else (filters or {})
    return get_pie_chart_data(f)