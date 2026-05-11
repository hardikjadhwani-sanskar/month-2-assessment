
import os

import frappe
import datetime
import json
from frappe import _
from frappe.utils import now_datetime, get_datetime, flt, cint
from frappe.model.document import Document
from frappe.utils import get_site_path
import base64
# ─────────────────────────────────────────────────────────────────────────────
# A) GET SEAT AVAILABILITY
# ─────────────────────────────────────────────────────────────────────────────


# API URL:
# /api/method/movie_tickets.movie_tickets.api.get_seat_availability
@frappe.whitelist()
def get_seat_availability(show_name):
    """
    Returns total rows, seats per row, and a 2D array of seat objects.
    Queries Confirmed and Pending bookings for the show to determine booked seats.
    """
    show = frappe.get_doc("Show", show_name)
    if not show:
        frappe.throw(_("Show {0} not found.").format(show_name))

    screen = frappe.get_doc("Screen", show.screen)
    rows       = cint(screen.seat_rows)
    seats_per_row = cint(screen.seats_per_row)

    # Fetch all submitted, non-cancelled bookings for this show
    bookings = frappe.get_all(
        "Ticket Booking",
        filters={
            "show":           show_name,
            "booking_status": ["in", ["Confirmed", "Pending"]],
            "docstatus":      ["!=", 2]
        },
        fields=["name"]
    )

    # Collect booked seat labels from each booking's child table
    booked_labels = set()
    for b in bookings:
        seats = frappe.get_all(
            "Booked Seat",
            filters={"parent": b.name},
            fields=["seat_label"]
        )
        for s in seats:
            if s.seat_label:
                booked_labels.add(s.seat_label)

    # Build 2D array — one list per row
    grid = []
    for r in range(rows):
        row_letter = chr(65 + r)   # A, B, C ...
        row_seats  = []
        for c in range(1, seats_per_row + 1):
            label  = f"{row_letter}-{c}"
            status = "booked" if label in booked_labels else "available"
            row_seats.append({"seat_label": label, "status": status})
        grid.append(row_seats)

    return {
        "show_name":     show_name,
        "total_rows":    rows,
        "seats_per_row": seats_per_row,
        "total_seats":   rows * seats_per_row,
        "available_seats": show.available_seats,
        "booked_seats":  show.booked_seats,
        "seat_grid":     grid
    }


# ─────────────────────────────────────────────────────────────────────────────
# B) CREATE BOOKING
# ─────────────────────────────────────────────────────────────────────────────

# API URL:
# /api/method/movie_tickets.movie_tickets.api.create_booking
@frappe.whitelist(allow_guest=False)
def create_booking(show, customer_name, customer_email, customer_phone, seats):
    """
    Creates a Ticket Booking with specified seats.
    Re-validates seat availability server-side using frappe.lock_doc to prevent race conditions.
    """
    if isinstance(seats, str):
        seats = json.loads(seats)

    if not seats:
        frappe.throw(_("Please select at least one seat."))

    # ── Lock the Show doc to prevent concurrent booking of same seats ─────────
        show_doc = frappe.get_doc(
        "Show",
        show,
        for_update=True
    )

    try:
        show_doc = frappe.get_doc("Show", show)

        if show_doc.show_status in ("Completed", "Cancelled"):
            frappe.throw(_("Bookings are not allowed for a {0} show.").format(show_doc.show_status))

        if show_doc.available_seats < len(seats):
            frappe.throw(_("Only {0} seat(s) available.").format(show_doc.available_seats))

        # ── Re-validate: check none of the requested seats are already booked ─
        existing_bookings = frappe.get_all(
            "Ticket Booking",
            filters={
                "show":           show,
                "booking_status": ["in", ["Confirmed", "Pending"]],
                "docstatus":      ["!=", 2]
            },
            fields=["name"]
        )

        already_booked = set()
        for b in existing_bookings:
            booked_seats = frappe.get_all(
                "Booked Seat",
                filters={"parent": b.name},
                fields=["seat_label"]
            )
            for s in booked_seats:
                already_booked.add(s.seat_label)

        requested_labels  = [s.get("seat_label") for s in seats]
        conflicting_seats = [lbl for lbl in requested_labels if lbl in already_booked]

        if conflicting_seats:
            frappe.throw(
                _("The following seat(s) were just booked by someone else: {0}. Please choose different seats.").format(
                    ", ".join(conflicting_seats)
                )
            )

        # ── Create the Ticket Booking doc ─────────────────────────────────────
        price_per_seat = flt(show_doc.ticket_price)
        total_amount   = price_per_seat * len(seats)

        doc = frappe.new_doc("Ticket Booking")
        doc.naming_series    = "BKG-.YYYY.-.#####"
        doc.show             = show
        doc.customer_name    = customer_name
        doc.customer_email   = customer_email
        doc.customer_phone   = customer_phone
        doc.booked_by        = frappe.session.user
        doc.booking_status   = "Pending"
        doc.payment_status   = "Unpaid"
        doc.booking_time     = now_datetime()
        doc.number_of_seats  = len(seats)
        doc.price_per_seat   = price_per_seat
        doc.total_amount     = total_amount

        for s in seats:
            label      = s.get("seat_label", "")
            row_letter, seat_num = (
                label.split("-")
                if label else ("", "")
            )

            doc.append("seats", {
                "seat_label":  label,
                "row_letter":  row_letter,
                "seat_number": cint(seat_num),
                "seat_price":  price_per_seat
            })

        doc.insert(ignore_permissions=False)
        doc.submit()

        # ── Update Show counters ──────────────────────────────────────────────
        frappe.db.set_value("Show", show, {
            "booked_seats":    (show_doc.booked_seats    or 0) + len(seats),
            "available_seats": (show_doc.available_seats or 0) - len(seats)
        })

        frappe.db.commit()
    
    except Exception as e:
        frappe.db.rollback()
        frappe.throw(_("An error occurred while creating the booking: {0}").format(str(e)))

    return {
        "success":      True,
        "booking_name": doc.name,
        "total_amount": total_amount,
        "seats_booked": requested_labels,
        "message":      "Booking created. Complete payment within 15 minutes."
    }


# ─────────────────────────────────────────────────────────────────────────────
# C) GET SHOWS FOR MOVIE
# ─────────────────────────────────────────────────────────────────────────────

# API URL:
# /api/method/movie_tickets.movie_tickets.api.get_shows_for_movie
@frappe.whitelist(allow_guest=True)
def get_shows_for_movie(movie, city=None, date=None):
    """
    Returns upcoming shows for a movie, optionally filtered by city and/or date.
    """
    filters = {
        "movie":       movie,
        "show_status": ["in", ["Scheduled", "Now Playing"]],
        "show_date":   [">=", datetime.date.today()]
    }

    if date:
        filters["show_date"] = date

    shows = frappe.get_all(
        "Show",
        filters=filters,
        fields=[
            "name", "theatre", "screen",
            "show_date", "start_time", "end_time",
            "ticket_price", "available_seats",
            "show_status", "movie_title"
        ],
        order_by="show_date asc, start_time asc"
    )

    if not shows:
        return []

    result = []
    for show in shows:
        # Fetch screen type from Screen doctype
        screen_type = frappe.db.get_value("Screen", show.screen, "screen_type") or "Standard"

        # Filter by city if provided — match against Theatre's city field
        if city:
            theatre_city = frappe.db.get_value("Theatre", show.theatre, "city")
            if theatre_city and theatre_city.lower() != city.lower():
                continue

        result.append({
            "show_name":       show.name,
            "movie_title":     show.movie_title,
            "theatre":         show.theatre,
            "screen":          show.screen,
            "screen_type":     screen_type,
            "show_date":       str(show.show_date),
            "start_time":      str(show.start_time),
            "end_time":        str(show.end_time) if show.end_time else None,
            "ticket_price":    flt(show.ticket_price),
            "available_seats": cint(show.available_seats),
            "show_status":     show.show_status
        })

    return result


# ─────────────────────────────────────────────────────────────────────────────
# D) SEND BOOKING CONFIRMATION EMAIL
# ─────────────────────────────────────────────────────────────────────────────

# API URL:
# /api/method/movie_tickets.movie_tickets.api.send_booking_confirmation
@frappe.whitelist()
def send_booking_confirmation(booking_name, qr_url=None):
    doc = frappe.get_doc("Ticket Booking", booking_name)

    if not doc.customer_email:
        frappe.throw(_("Customer email is missing on booking {0}.").format(booking_name))

    # Use stored QR URL if not passed directly
    if not qr_url:
        qr_url = doc.qr_code_url

    seat_labels = ", ".join([s.seat_label for s in (doc.seats or [])])

    # Convert QR image to Base64
    qr_base64 = ""

    if qr_url:

        file_path = get_site_path(
            "public",
            qr_url.lstrip("/")
        )

        if os.path.exists(file_path):

            with open(file_path, "rb") as f:

                qr_base64 = (
                    base64.b64encode(
                        f.read()
                    ).decode()
                )

    # Inline image HTML
    qr_img_tag = (
        f"""
        <img
            src="data:image/png;base64,{qr_base64}"
            width="160"
            height="160"
            alt="Booking QR Code"
            style="display:block;margin:0 auto;"
        />
        """
        if qr_base64
        else
        """
        <p style='color:#999;font-size:12px;'>
            QR code not available
        </p>
        """
    )

    # # Build absolute URL for QR image
    # site_url   = frappe.utils.get_url()
    # qr_img_tag = (
    #     f'<img src="{site_url}{qr_url}" width="160" height="160" '
    #     f'alt="Booking QR Code" style="display:block;margin:0 auto;"/>'
    #     if qr_url else
    #     "<p style='color:#999;font-size:12px;'>QR code not available</p>"
    # )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:auto;
                border:1px solid #e0e0e0;border-radius:8px;overflow:hidden;">
        <div style="background:#1a1a2e;padding:24px 32px;">
            <h1 style="color:#fff;margin:0;font-size:22px;">🎬 Booking Confirmed!</h1>
            <p style="color:#a0a0c0;margin:6px 0 0;">Your tickets are ready.</p>
        </div>
        <div style="background:#f0f4ff;padding:14px 32px;border-bottom:1px solid #dce3f5;">
            <p style="margin:0;font-size:13px;color:#555;">Booking ID</p>
            <p style="margin:4px 0 0;font-size:20px;font-weight:bold;
                      color:#1a1a2e;letter-spacing:1px;">{doc.name}</p>
        </div>
        <div style="padding:24px 32px;">
            <table style="width:100%;border-collapse:collapse;font-size:14px;">
                <tr><td style="padding:8px 0;color:#777;width:40%;
                    border-bottom:1px solid #f0f0f0;">Movie</td>
                    <td style="padding:8px 0;font-weight:600;color:#1a1a2e;
                    border-bottom:1px solid #f0f0f0;">{doc.movie_title}</td></tr>
                <tr><td style="padding:8px 0;color:#777;
                    border-bottom:1px solid #f0f0f0;">Theatre</td>
                    <td style="padding:8px 0;font-weight:600;color:#1a1a2e;
                    border-bottom:1px solid #f0f0f0;">{doc.theatre}</td></tr>
                <tr><td style="padding:8px 0;color:#777;
                    border-bottom:1px solid #f0f0f0;">Screen</td>
                    <td style="padding:8px 0;font-weight:600;color:#1a1a2e;
                    border-bottom:1px solid #f0f0f0;">{doc.screen}</td></tr>
                <tr><td style="padding:8px 0;color:#777;
                    border-bottom:1px solid #f0f0f0;">Date & Time</td>
                    <td style="padding:8px 0;font-weight:600;color:#1a1a2e;
                    border-bottom:1px solid #f0f0f0;">
                    {frappe.format(doc.show_date, {"fieldtype":"Date"})}
                    at {str(doc.start_time)[:5]}</td></tr>
                <tr><td style="padding:8px 0;color:#777;
                    border-bottom:1px solid #f0f0f0;">Seats</td>
                    <td style="padding:8px 0;font-weight:600;color:#1a1a2e;
                    border-bottom:1px solid #f0f0f0;">{seat_labels}</td></tr>
                <tr><td style="padding:8px 0;color:#777;">Amount</td>
                    <td style="padding:8px 0;font-size:16px;font-weight:bold;
                    color:#2d7a2d;">₹{doc.total_amount:,.2f}</td></tr>
            </table>
        </div>
        <!-- QR Code Section -->
        <div style="padding:20px 32px;text-align:center;
                    border-top:1px solid #e0e0e0;background:#fafafa;">
            <p style="margin:0 0 12px;font-size:13px;color:#555;font-weight:600;">
                Show this QR code at the entrance
            </p>
            {qr_img_tag}
        </div>
        <div style="background:#f5f5f5;padding:16px 32px;text-align:center;
                    border-top:1px solid #e0e0e0;">
            <p style="margin:0;font-size:12px;color:#999;">
                © {frappe.utils.now_datetime().year} Movie Tickets
            </p>
        </div>
    </div>
    """

    frappe.sendmail(
        recipients=[doc.customer_email],
        subject=f"Booking Confirmed — {doc.movie_title} | {doc.name}",
        message=html,
        now=True
    )

    return {"success": True, "message": f"Confirmation sent to {doc.customer_email}"}

# ─────────────────────────────────────────────────────────────────────────────
# E) GET REVENUE SUMMARY
# ─────────────────────────────────────────────────────────────────────────────


# API URL:
# /api/method/movie_tickets.movie_tickets.api.get_revenue_summary
@frappe.whitelist()
def get_revenue_summary(theater=None, from_date=None, to_date=None):
    """
    Returns total_bookings, total_revenue, total_seats_sold,
    avg_occupancy_pct, and top_movie by revenue.
    Uses parameterized SQL queries throughout.
    """
    conditions = ["tb.docstatus = 1", "tb.booking_status != 'Cancelled'"]
    params     = {}

    if theater:
        conditions.append("tb.theatre = %(theatre)s")
        params["theatre"] = theater

    if from_date:
        conditions.append("tb.show_date >= %(from_date)s")
        params["from_date"] = from_date

    if to_date:
        conditions.append("tb.show_date <= %(to_date)s")
        params["to_date"] = to_date

    where_clause = " AND ".join(conditions)

    # ── Main summary ──────────────────────────────────────────────────────────
    summary = frappe.db.sql(f"""
        SELECT
            COUNT(tb.name)              AS total_bookings,
            SUM(tb.total_amount)        AS total_revenue,
            SUM(tb.number_of_seats)     AS total_seats_sold
        FROM
            `tabTicket Booking` tb
        WHERE
            {where_clause}
    """, params, as_dict=True)

    total_bookings   = cint(summary[0].total_bookings)   if summary else 0
    total_revenue    = flt(summary[0].total_revenue)     if summary else 0.0
    total_seats_sold = cint(summary[0].total_seats_sold) if summary else 0

    # ── Average occupancy across all shows in the filtered range ─────────────
    occupancy = frappe.db.sql(f"""
        SELECT
            AVG(
                CASE
                    WHEN s.total_seats > 0
                    THEN (s.booked_seats / s.total_seats) * 100
                    ELSE 0
                END
            ) AS avg_occupancy_pct
        FROM
            `tabShow` s
        INNER JOIN
            `tabTicket Booking` tb ON tb.show = s.name
        WHERE
            {where_clause}
    """, params, as_dict=True)

    avg_occupancy_pct = round(flt(occupancy[0].avg_occupancy_pct), 2) if occupancy else 0.0

    # ── Top movie by revenue ──────────────────────────────────────────────────
    top_movie_rows = frappe.db.sql(f"""
        SELECT
            tb.movie_title,
            SUM(tb.total_amount)    AS revenue,
            COUNT(tb.name)          AS bookings,
            SUM(tb.number_of_seats) AS seats_sold
        FROM
            `tabTicket Booking` tb
        WHERE
            {where_clause}
        GROUP BY
            tb.movie_title
        ORDER BY
            revenue DESC
        LIMIT 1
    """, params, as_dict=True)

    top_movie = None
    if top_movie_rows:
        row = top_movie_rows[0]
        top_movie = {
            "movie_title": row.movie_title,
            "revenue":     flt(row.revenue),
            "bookings":    cint(row.bookings),
            "seats_sold":  cint(row.seats_sold)
        }

    return {
        "total_bookings":    total_bookings,
        "total_revenue":     total_revenue,
        "total_seats_sold":  total_seats_sold,
        "avg_occupancy_pct": avg_occupancy_pct,
        "top_movie":         top_movie,
        "filters_applied": {
            "theater":   theater,
            "from_date": from_date,
            "to_date":   to_date
        }
    }

