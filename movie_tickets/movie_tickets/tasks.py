# movie_tickets/tasks.py

import frappe
import datetime
from frappe.utils import today, now_datetime, getdate, get_datetime, nowtime

#import booking_expiry_minutes from booking_configuration doctype
def get_booking_expiry_minutes():
	config = frappe.get_single("Booking Configuration")
	return config.booking_expiry_minutes or 15  # default to 15 if not set

def auto_expire_unpaid_bookings():
    """
    Called every 5 minutes via cron.
    Finds Pending + Unpaid bookings older than booking_expiry_minutes
    and marks them Expired, releasing seats back to the Show.
    """
    expiry_minutes = get_booking_expiry_minutes()

    # Find all pending unpaid submitted bookings
    expired_bookings = frappe.db.sql("""
        SELECT
            name,
            `show`,
            number_of_seats,
            booking_time
           
        FROM
            `tabTicket Booking`
        WHERE
            booking_status  = 'Pending'
            AND payment_status  = 'Unpaid'
            AND booking_time <= (NOW() - INTERVAL %(expiry)s MINUTE)
    """, {"expiry": expiry_minutes}, as_dict=True)

    if not expired_bookings:
        return

    for booking in expired_bookings:
        try:
            # Mark booking as Expired
            frappe.db.set_value("Ticket Booking", booking.name, {
                "booking_status": "Expired"
            })

            # Release seats back to the Show
            show = frappe.db.get_value(
                "Show",
                booking.show,
                ["booked_seats", "available_seats"],
                as_dict=True
            )

            if show:
                frappe.db.set_value("Show", booking.show, {
                    "booked_seats":    max((show.booked_seats    or 0) - (booking.number_of_seats or 0), 0),
                    "available_seats": (show.available_seats or 0) + (booking.number_of_seats or 0)
                })

            frappe.logger().info(
                f"[Auto Expire] Booking {booking.name} expired. "
                f"{booking.number_of_seats} seat(s) released for Show {booking.show}."
            )

        except Exception as e:
            # Log error but continue processing remaining bookings
            frappe.logger().error(
                f"[Auto Expire] Failed to expire booking {booking.name}: {str(e)}"
            )
            frappe.db.rollback()
            continue

    frappe.db.commit()

# ─────────────────────────────────────────────────────────────────────────────
# B) UPDATE MOVIE STATUS — runs daily
# ─────────────────────────────────────────────────────────────────────────────

def update_movie_status():
    """
    Recalculates movie_status for all movies based on
    today vs release_date and end_date.
    """
    today_date = getdate(today())

    movies = frappe.db.sql("""
        SELECT name, release_date, end_date, movie_status
        FROM `tabMovie`
        WHERE docstatus != 2
    """, as_dict=True)

    if not movies:
        return

    updated = 0

    for movie in movies:
        release_date = getdate(movie.release_date) if movie.release_date else None
        end_date     = getdate(movie.end_date)     if movie.end_date     else None

        if not release_date:
            new_status = "Upcoming"
        elif today_date < release_date:
            new_status = "Upcoming"
        elif end_date and today_date > end_date:
            new_status = "Ended"
        else:
            new_status = "Now Showing"

        # Only write to DB if status actually changed — avoids unnecessary writes
        if new_status != movie.movie_status:
            frappe.db.set_value("Movie", movie.name, "movie_status", new_status)
            updated += 1
            frappe.logger().info(
                f"[Movie Status] {movie.name}: {movie.movie_status} → {new_status}"
            )

    frappe.db.commit()
    frappe.logger().info(f"[Movie Status] Done. {updated} movie(s) updated.")


# ─────────────────────────────────────────────────────────────────────────────
# C) UPDATE SHOW STATUS — runs hourly
# ─────────────────────────────────────────────────────────────────────────────

def update_show_status():
    """
    - Shows where show_date = today, start_time passed, end_time not yet → Now Playing
    - Shows where end_time passed today                                  → Completed
    - Past-date Scheduled shows                                          → Completed
    """
    now         = now_datetime()
    today_date  = getdate(today())
    current_time = now.time()

    shows = frappe.db.sql("""
        SELECT name, show_date, start_time, end_time, show_status
        FROM `tabShow`
        WHERE
            show_status NOT IN ('Cancelled', 'Completed')
            AND docstatus != 2
    """, as_dict=True)

    if not shows:
        return

    updated = 0

    for show in shows:
        show_date  = getdate(show.show_date) if show.show_date else None
        start_time = show.start_time
        end_time   = show.end_time

        if not show_date:
            continue

        new_status = show.show_status  # default — no change

        if show_date < today_date:
            # Past date — any non-completed show should be Completed
            new_status = "Completed"

        elif show_date == today_date:
            if end_time and current_time > (datetime.datetime.min + end_time).time():
                # end_time has passed today → Completed
                new_status = "Completed"

            elif start_time and current_time >= (datetime.datetime.min + start_time).time():
                # start_time passed but end_time not yet → Now Playing
                new_status = "Now Playing"

        # Only write if status changed
        if new_status != show.show_status:
            frappe.db.set_value("Show", show.name, "show_status", new_status)
            updated += 1
            frappe.logger().info(
                f"[Show Status] {show.name} ({show_date}): {show.show_status} → {new_status}"
            )

    frappe.db.commit()
    frappe.logger().info(f"[Show Status] Done. {updated} show(s) updated.")


# ─────────────────────────────────────────────────────────────────────────────
# D) DAILY REVENUE DIGEST — runs at 11 PM
# ─────────────────────────────────────────────────────────────────────────────

def send_daily_revenue_digest():
    """
    Calculates today's total bookings, revenue, and top movie.
    Sends an HTML digest email to all Cinema Managers.
    """
    today_date = today()

    # ── Fetch today's summary ─────────────────────────────────────────────────
    summary = frappe.db.sql("""
        SELECT
            COUNT(name)          AS total_bookings,
            SUM(total_amount)    AS total_revenue,
            SUM(number_of_seats) AS total_seats_sold
        FROM
            `tabTicket Booking`
        WHERE
            DATE(booking_time)  = %(today)s
            AND booking_status  != 'Cancelled'
            AND booking_status  != 'Expired'
            AND docstatus        = 1
    """, {"today": today_date}, as_dict=True)

    total_bookings   = summary[0].total_bookings   or 0 if summary else 0
    total_revenue    = summary[0].total_revenue    or 0 if summary else 0
    total_seats_sold = summary[0].total_seats_sold or 0 if summary else 0

    # ── Top movie by revenue today ────────────────────────────────────────────
    top_movie_row = frappe.db.sql("""
        SELECT
            movie_title,
            SUM(total_amount)    AS revenue,
            COUNT(name)          AS bookings,
            SUM(number_of_seats) AS seats_sold
        FROM
            `tabTicket Booking`
        WHERE
            DATE(booking_time)  = %(today)s
            AND booking_status  != 'Cancelled'
            AND booking_status  != 'Expired'
            AND docstatus        = 1
        GROUP BY
            movie_title
        ORDER BY
            revenue DESC
        LIMIT 1
    """, {"today": today_date}, as_dict=True)

    top_movie = top_movie_row[0] if top_movie_row else None

    # ── Get Cinema Manager email addresses ────────────────────────────────────
    managers = frappe.db.sql("""
        SELECT DISTINCT u.email
        FROM `tabUser` u
        INNER JOIN `tabHas Role` r ON r.parent = u.name
        WHERE
            r.role       = 'Cinema Manager'
            AND u.enabled = 1
            AND u.email  != ''
    """, as_dict=True)

    if not managers:
        frappe.logger().warning("[Revenue Digest] No Cinema Managers found to send digest to.")
        return

    recipients = [m.email for m in managers]

    # ── Build HTML email ──────────────────────────────────────────────────────
    top_movie_html = f"""
        <tr>
            <td style="padding:10px 0;color:#777;border-bottom:1px solid #f0f0f0;">Top Movie</td>
            <td style="padding:10px 0;font-weight:600;color:#1a1a2e;border-bottom:1px solid #f0f0f0;">
                {top_movie.movie_title}
            </td>
        </tr>
        <tr>
            <td style="padding:10px 0;color:#777;border-bottom:1px solid #f0f0f0;">Top Movie Revenue</td>
            <td style="padding:10px 0;font-weight:600;color:#2d7a2d;border-bottom:1px solid #f0f0f0;">
                ₹{top_movie.revenue:,.2f}
            </td>
        </tr>
        <tr>
            <td style="padding:10px 0;color:#777;">Top Movie Bookings</td>
            <td style="padding:10px 0;font-weight:600;color:#1a1a2e;">
                {top_movie.bookings} booking(s) / {top_movie.seats_sold} seat(s)
            </td>
        </tr>
    """ if top_movie else """
        <tr>
            <td colspan="2" style="padding:10px 0;color:#777;">No bookings today.</td>
        </tr>
    """

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;
                border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">

        <!-- Header -->
        <div style="background:#1a1a2e;padding:24px 32px;">
            <h1 style="color:#ffffff;margin:0;font-size:20px;">📊 Daily Revenue Digest</h1>
            <p style="color:#a0a0c0;margin:6px 0 0;">
                Summary for <strong style="color:#fff;">{today_date}</strong>
            </p>
        </div>

        <!-- Summary Cards -->
        <div style="display:flex;gap:0;border-bottom:1px solid #e0e0e0;">
            <div style="flex:1;padding:20px 24px;text-align:center;border-right:1px solid #e0e0e0;">
                <p style="margin:0;font-size:12px;color:#777;text-transform:uppercase;letter-spacing:1px;">
                    Total Bookings
                </p>
                <p style="margin:8px 0 0;font-size:28px;font-weight:bold;color:#1a1a2e;">
                    {total_bookings}
                </p>
            </div>
            <div style="flex:1;padding:20px 24px;text-align:center;border-right:1px solid #e0e0e0;">
                <p style="margin:0;font-size:12px;color:#777;text-transform:uppercase;letter-spacing:1px;">
                    Total Revenue
                </p>
                <p style="margin:8px 0 0;font-size:28px;font-weight:bold;color:#2d7a2d;">
                    ₹{total_revenue:,.2f}
                </p>
            </div>
            <div style="flex:1;padding:20px 24px;text-align:center;">
                <p style="margin:0;font-size:12px;color:#777;text-transform:uppercase;letter-spacing:1px;">
                    Seats Sold
                </p>
                <p style="margin:8px 0 0;font-size:28px;font-weight:bold;color:#1a1a2e;">
                    {total_seats_sold}
                </p>
            </div>
        </div>

        <!-- Top Movie Breakdown -->
        <div style="padding:24px 32px;">
            <h2 style="font-size:15px;color:#1a1a2e;margin:0 0 12px;">🏆 Top Performer</h2>
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                {top_movie_html}
            </table>
        </div>

        <!-- Footer -->
        <div style="background:#f5f5f5;padding:16px 32px;text-align:center;
                    border-top:1px solid #e0e0e0;">
            <p style="margin:0;font-size:12px;color:#999;">
                This is an automated digest generated at 11:00 PM.<br>
                © {datetime.datetime.now().year} Movie Tickets. All rights reserved.
            </p>
        </div>

    </div>
    """

    frappe.sendmail(
        recipients=recipients,
        subject=f"Daily Revenue Digest — {today_date}",
        message=html,
        now=True
    )

    frappe.logger().info(
        f"[Revenue Digest] Sent to {recipients}. "
        f"Bookings: {total_bookings}, Revenue: {total_revenue}, Seats: {total_seats_sold}"
    )