import frappe

def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.response["type"]     = "redirect"
        frappe.local.response["location"] = "/login?redirect-to=/my-bookings"
        return

    bookings_raw = frappe.get_all(
        "Ticket Booking",
        filters={"owner": frappe.session.user},
        fields=[
            "name", "show", "movie_title",
            "number_of_seats", "total_amount",
            "booking_status", "payment_status",
            "creation"
        ],
        order_by="creation desc"
    )

    bookings = []
    for b in bookings_raw:
        # Get show details: date, time, theatre
        show_data = {}
        if b.get("show"):
            show_data = frappe.db.get_value(
                "Show", b.show,
                ["show_date", "start_time", "theatre"],
                as_dict=True
            ) or {}
            # Resolve theatre display name
            if show_data.get("theatre"):
                show_data["theatre_name"] = (
                    frappe.db.get_value("Theatre", show_data["theatre"], "theatre_name")
                    or show_data["theatre"]
                )

        # Get seat labels from child table
        seats = frappe.get_all(
            "Booked Seat",           
            filters={"parent": b.name},
            fields=["seat_label"],
            order_by="idx asc"
        )
        seat_str = ", ".join(s.seat_label for s in seats) if seats else "—"

        bookings.append({
            "name":           b.name,
            "show":           b.get("show"),
            "movie_title":    b.get("movie_title") or "—",
            "show_date":      show_data.get("show_date"),
            "show_time":      show_data.get("start_time"),
            "theatre_name":   show_data.get("theatre_name", "—"),
            "seat_labels":    seat_str,
            "number_of_seats": b.get("number_of_seats", 0),
            "total_amount":   b.get("total_amount", 0),
            "booking_status": b.get("booking_status", "—"),
            "payment_status": b.get("payment_status", "—"),
            "creation":       b.get("creation"),
        })

    context.bookings = bookings
    context.title    = "My Bookings"