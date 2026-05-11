
import frappe


def execute():
    """
    Patch: Recalculate booked_seats and available_seats for all Shows
    by counting actual seats from Confirmed and Pending Ticket Bookings.

    Why this is needed:
        If bookings were created/cancelled outside normal workflows
        (e.g. data imports, manual DB edits, failed transactions),
        the Show counters may be out of sync with reality.
        This patch resets them to the ground truth.
    """

    shows = frappe.db.sql("""
        SELECT name, total_seats
        FROM `tabShow`
        WHERE docstatus != 2
    """, as_dict=True)

    if not shows:
        frappe.logger().info("[Patch] recalculate_show_seat_counts: No shows found.")
        return

    updated = 0

    for show in shows:
        total_seats = show.total_seats or 0

        # Count actual booked seats from submitted, non-cancelled bookings
        result = frappe.db.sql("""
            SELECT COALESCE(SUM(tb.number_of_seats), 0) AS booked
            FROM `tabTicket Booking` tb
            WHERE
                tb.show           = %(show)s
                AND tb.booking_status IN ('Confirmed', 'Pending')
                AND tb.docstatus  != 2
        """, {"show": show.name}, as_dict=True)

        actual_booked    = int(result[0].booked) if result else 0
        actual_available = max(total_seats - actual_booked, 0)

        frappe.db.set_value("Show", show.name, {
            "booked_seats":    actual_booked,
            "available_seats": actual_available
        }, update_modified=False)

        frappe.logger().info(
            f"[Patch] Show {show.name}: "
            f"booked={actual_booked}, available={actual_available}, total={total_seats}"
        )

        updated += 1

    frappe.db.commit()
    frappe.logger().info(
        f"[Patch] recalculate_show_seat_counts: {updated} show(s) updated."
    )