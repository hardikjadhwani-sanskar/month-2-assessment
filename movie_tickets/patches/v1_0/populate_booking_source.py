
import frappe


def execute():
    """
    Patch: Set booking_source = 'Counter' for all existing Ticket Bookings
    where the booking_source custom field is NULL or empty.

    Why this is needed:
        The booking_source field was added after the app went live.
        All pre-existing bookings were created at the counter by staff
        (the app had no online booking at that point), so 'Counter'
        is the correct default to backfill.


    """

    # Verify the field exists before attempting to write
    field_exists = frappe.db.sql("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE
            TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME  = 'tabTicket Booking'
            AND COLUMN_NAME = 'booking_source'
    """, as_dict=True)

    if not field_exists or field_exists[0].cnt == 0:
        frappe.logger().error(
            "[Patch] populate_booking_source: "
            "Column 'booking_source' does not exist on tabTicket Booking. "
            "Add the custom field and run bench migrate before this patch."
        )
        return

    # Fetch all bookings with no booking_source
    bookings = frappe.db.sql("""
        SELECT name
        FROM `tabTicket Booking`
        WHERE
            (booking_source IS NULL OR booking_source = '')
            
    """, as_dict=True)

    if not bookings:
        frappe.logger().info(
            "[Patch] populate_booking_source: No bookings need updating."
        )
        return

    total = len(bookings)

    # Bulk update in one query — far faster than looping set_value for large datasets
    frappe.db.sql("""
        UPDATE `tabTicket Booking`
        SET booking_source = 'Counter'
        WHERE
            (booking_source IS NULL OR booking_source = '')
            
    """)

    frappe.db.commit()

    frappe.logger().info(
        f"[Patch] populate_booking_source: {total} booking(s) set to 'Counter'."
    )