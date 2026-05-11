# movie_tickets/bulk_show_creator.py

import frappe
import datetime
from frappe import _
from frappe.utils import getdate, add_days


@frappe.whitelist()
def create_shows_bulk(movie, screens, date_from, date_to, show_times, ticket_price):
    """
    Accepts a movie, list of screens, date range, and show times.
    Enqueues a background job to create all Show records in bulk.

    Args:
        movie        : Movie docname
        screens      : JSON list of screen names e.g. ["Screen 1", "Screen 2"]
        date_from    : Start date string "YYYY-MM-DD"
        date_to      : End date string "YYYY-MM-DD"
        show_times   : JSON list of HH:MM strings e.g. ["10:00", "14:00", "19:00"]
        ticket_price : float
    """
    import json

    if isinstance(screens, str):
        screens = json.loads(screens)
    if isinstance(show_times, str):
        show_times = json.loads(show_times)

    # Basic validation before enqueue
    if not screens:
        frappe.throw(_("Please select at least one screen."))
    if not show_times:
        frappe.throw(_("Please provide at least one show time."))
    if getdate(date_from) > getdate(date_to):
        frappe.throw(_("From Date must be before or equal to To Date."))

    # Estimate count for user feedback
    delta      = (getdate(date_to) - getdate(date_from)).days + 1
    total      = delta * len(screens) * len(show_times)
    max_shows  = 500

    if total > max_shows:
        frappe.throw(
            _(f"This would create {total} shows which exceeds the limit of {max_shows}. "
              "Please reduce the date range, screens, or show times.")
        )

    # Enqueue the actual creation as a background job
    frappe.enqueue(
        "movie_tickets.movie_tickets.bulk_show_creator._create_shows_background",
        queue="long",
        timeout=600,
        job_name=f"Bulk Show Creator — {movie}",
        movie=movie,
        screens=screens,
        date_from=date_from,
        date_to=date_to,
        show_times=show_times,
        ticket_price=ticket_price,
        enqueued_by=frappe.session.user
    )

    return {
        "success": True,
        "message": f"Creating {total} show(s) in the background. You will be notified when done.",
        "estimated_count": total
    }


def _create_shows_background(
    movie, screens, date_from, date_to,
    show_times, ticket_price, enqueued_by
):
    """
    Background worker — called by frappe.enqueue.
    Creates Show records for every combination of
    screen × date × show_time in the given range.
    """
    from frappe.utils import get_datetime

    created   = 0
    skipped   = 0
    errors    = []

    current_date = getdate(date_from)
    end_date     = getdate(date_to)

    while current_date <= end_date:
        for screen_name in screens:

            # Fetch screen details
            screen = frappe.get_doc("Screen", screen_name)

            for time_str in show_times:
                try:
                    hour, minute = map(int, time_str.split(":"))
                    start_td = datetime.timedelta(hours=hour, minutes=minute)

                    # Fetch movie duration for end_time calculation
                    duration = frappe.db.get_value("Movie", movie, "duration_minutes") or 120
                    end_td   = start_td + datetime.timedelta(minutes=duration + 20)  # +20 min buffer

                    # Check for schedule conflict on this screen/date
                    conflict = frappe.db.sql("""
                        SELECT name FROM `tabShow`
                        WHERE
                            screen    = %(screen)s
                            AND show_date = %(date)s
                            AND show_status NOT IN ('Cancelled')
                            AND docstatus != 2
                            AND (
                                (start_time < %(end_time)s AND end_time > %(start_time)s)
                            )
                        LIMIT 1
                    """, {
                        "screen":     screen_name,
                        "date":       current_date,
                        "start_time": start_td,
                        "end_time":   end_td
                    })

                    if conflict:
                        skipped += 1
                        frappe.logger().warning(
                            f"[Bulk Show] Skipped {screen_name} {current_date} {time_str} "
                            f"— conflicts with {conflict[0][0]}"
                        )
                        continue

                    # Create the Show
                    show = frappe.new_doc("Show")
                    show.naming_series   = "SHW-.YYYY.-.#####"
                    show.movie           = movie
                    show.screen          = screen_name
                    show.theatre         = screen.theatre
                    show.show_date       = current_date
                    show.start_time      = start_td
                    show.end_time        = end_td
                    show.total_seats     = screen.total_seats
                    show.available_seats = screen.total_seats
                    show.booked_seats    = 0
                    show.ticket_price    = ticket_price
                    show.show_status     = "Scheduled"
                    show.insert(ignore_permissions=True)

                    created += 1

                except Exception as e:
                    errors.append(f"{screen_name} {current_date} {time_str}: {str(e)}")
                    frappe.logger().error(f"[Bulk Show] Error: {e}")

        current_date = add_days(current_date, 1)

    frappe.db.commit()

    # Notify the user who triggered the job
    summary = (
        f"Bulk Show Creation Done.\n"
        f"✅ Created: {created}\n"
        f"⏭ Skipped (conflicts): {skipped}\n"
        f"❌ Errors: {len(errors)}"
    )

    frappe.sendmail(
        recipients=[frappe.db.get_value("User", enqueued_by, "email")],
        subject="Bulk Show Creation Complete",
        message=f"<pre>{summary}</pre>",
        now=True
    )

    frappe.logger().info(f"[Bulk Show] {summary}")