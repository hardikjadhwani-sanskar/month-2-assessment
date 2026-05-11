# cinema_dashboard.py

import frappe
from frappe.utils import today, add_days


@frappe.whitelist()
def get_dashboard_data():
    today_date = today()
    thirty_days_ago = add_days(today_date, -30)

    # 1. Today's occupancy by theatre
    occupancy = frappe.db.sql("""
        SELECT
            tb.theatre,
            SUM(s.total_seats)    AS total_seats,
            SUM(s.booked_seats)   AS booked_seats,
            ROUND(
                (SUM(s.booked_seats) / NULLIF(SUM(s.total_seats), 0)) * 100, 1
            ) AS occupancy_pct
        FROM `tabShow` s
        INNER JOIN `tabTicket Booking` tb ON tb.show = s.name
        WHERE
            s.show_date = %(today)s
            AND tb.docstatus = 1
            AND tb.booking_status != 'Cancelled'
        GROUP BY tb.theatre
    """, {"today": today_date}, as_dict=True)

    # 2. 30-day revenue trend
    revenue_trend = frappe.db.sql("""
        SELECT
            DATE(booking_time) AS date,
            SUM(total_amount)  AS revenue,
            COUNT(name)        AS bookings
        FROM `tabTicket Booking`
        WHERE
            booking_time   >= %(from_date)s
            AND booking_status != 'Cancelled'
            AND booking_status != 'Expired'
            AND docstatus   = 1
        GROUP BY DATE(booking_time)
        ORDER BY date ASC
    """, {"from_date": thirty_days_ago}, as_dict=True)

    # 3. Bookings by time slot (histogram)
    time_slots = frappe.db.sql("""
        SELECT
            CASE
                WHEN HOUR(s.start_time) BETWEEN 6  AND 11 THEN 'Morning (6–12)'
                WHEN HOUR(s.start_time) BETWEEN 12 AND 14 THEN 'Noon (12–15)'
                WHEN HOUR(s.start_time) BETWEEN 15 AND 17 THEN 'Afternoon (15–18)'
                WHEN HOUR(s.start_time) BETWEEN 18 AND 20 THEN 'Evening (18–21)'
                ELSE 'Night (21+)'
            END AS time_slot,
            COUNT(tb.name)        AS bookings,
            SUM(tb.total_amount)  AS revenue
        FROM `tabTicket Booking` tb
        INNER JOIN `tabShow` s ON s.name = tb.show
        WHERE
            tb.booking_time   >= %(from_date)s
            AND tb.booking_status != 'Cancelled'
            AND tb.docstatus   = 1
        GROUP BY time_slot
        ORDER BY MIN(HOUR(s.start_time))
    """, {"from_date": thirty_days_ago}, as_dict=True)

    # 4. Top 5 movies by bookings
    top_movies = frappe.db.sql("""
        SELECT
            movie_title,
            COUNT(name)          AS bookings,
            SUM(total_amount)    AS revenue,
            SUM(number_of_seats) AS seats_sold
        FROM `tabTicket Booking`
        WHERE
            booking_time   >= %(from_date)s
            AND booking_status != 'Cancelled'
            AND docstatus   = 1
        GROUP BY movie_title
        ORDER BY bookings DESC
        LIMIT 5
    """, {"from_date": thirty_days_ago}, as_dict=True)

    return {
        "occupancy_by_theatre": occupancy,
        "revenue_trend":        revenue_trend,
        "bookings_by_timeslot": time_slots,
        "top_movies":           top_movies
    }