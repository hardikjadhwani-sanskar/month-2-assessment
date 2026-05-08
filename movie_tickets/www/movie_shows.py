import frappe
from frappe.utils import nowdate

def get_context(context):
    context.no_cache = 1
    movie_id = frappe.form_dict.get("movie")

    if not movie_id:
        frappe.throw("Movie not specified", frappe.DoesNotExistError)

    movie = frappe.get_doc("Movie", movie_id)
    context.movie = movie

    shows = frappe.get_all(
        "Show",
        filters={
            "movie":       movie_id,
            "show_date":   [">=", nowdate()],
            "show_status": ["in", ["Scheduled", "Now Playing"]],
            
        },
        fields=[
            "name", "theatre", "screen",
            "show_date", "start_time",
            "ticket_price", "available_seats", "total_seats"
        ],
        order_by="show_date asc, start_time asc"
    )

    # Resolve theatre name (theatre is a Link field → Theatre doctype)
    for show in shows:
        show["theatre_name"] = frappe.db.get_value("Theatre", show.theatre, "theatre_name") or show.theatre
        show["screen_name"]  = frappe.db.get_value("Screen",  show.screen,  "screen_name")  or show.screen

    # Group: theatre → date → [shows]
    grouped = {}
    for show in shows:
        t = show.theatre_name
        d = str(show.show_date)
        grouped.setdefault(t, {}).setdefault(d, []).append(show)

    context.grouped_shows = grouped
    context.is_guest       = frappe.session.user == "Guest"
    context.title          = f"{movie.title} – Shows"