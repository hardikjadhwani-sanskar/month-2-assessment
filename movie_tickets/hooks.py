app_name = "movie_tickets"
app_title = "Movie Tickets"
app_publisher = "hardik"
app_description = "custom app for ticket booking system"
app_email = "hardik.jadhwani@sanskartechnolab.com"
app_license = "mit"


fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Movie Tickets"]]},
    {
        "dt": "Property Setter",
        "filters": [
            ["doc_type", "=", "Show"]
        ]
    }
            ]

permission_query_conditions = {
    "Ticket Booking":
    "movie_tickets.movie_tickets.doctype.ticket_booking.ticket_booking.get_permission_query_conditions"
}

has_permission = {
    "Ticket Booking":
    "movie_tickets.movie_tickets.doctype.ticket_booking.ticket_booking.has_permission"
}

website_context = {
    "top_bar_items": [
        {"label": "Now Showing", "url": "/now_showing"},
        {"label": "My Bookings", "url": "/my_bookings"},
    ]
}



scheduler_events = {
    "daily": [
        "movie_tickets.movie_tickets.tasks.update_movie_status",
    ],
    "hourly": [
        "movie_tickets.movie_tickets.tasks.update_show_status",
    ],
    "cron": {
        "*/5 * * * *": [
            "movie_tickets.movie_tickets.tasks.auto_expire_unpaid_bookings"
        ],
        "0 23 * * *": [
            "movie_tickets.movie_tickets.tasks.send_daily_revenue_digest"
        ]
    }
}

app_include_css = [
    "/assets/movie_tickets/css/cinema.css"
]

app_include_js = [
    "/assets/movie_tickets/js/cinema.js"
]


# ── Override Whitelisted Methods ──────────────────────────────────────────────
#
# WHAT IT DOES:
#   Replaces frappe.client.get_count with our wrapper function.
#   Every call to frappe.client.get_count anywhere in the app now
#   goes through logged_get_count() first, which logs the doctype
#   and filters before delegating to the original function.
#
# USE CASES:
#   - Auditing: track which doctypes are being queried and how often
#   - Debugging: log slow or unexpected count queries in production
#   - Rate limiting: add throttling before expensive COUNT(*) queries
#   - Analytics: measure feature usage by counting form loads per doctype
#
# RISKS:
#   - Any bug in your wrapper breaks ALL get_count calls site-wide
#   - Performance: your wrapper adds overhead to every single call
#   - Maintenance: must be kept in sync if Frappe changes the original signature
#   - Testing: harder to unit-test because the override is global
#
# WHEN TO USE vs ALTERNATIVES:
#   Use override_whitelisted_methods when:
#     → You need to intercept every call including from other apps
#     → You want zero changes to calling code
#   Use a custom whitelisted method instead when:
#     → You only need this for your own app's calls
#     → You want to avoid global side effects
#   Use frappe.monitor / frappe.db hooks instead when:
#     → You only need DB-level query logging (not API-level)
#
override_whitelisted_methods = {
    "frappe.client.get_count": "movie_tickets.movie_tickets.overrides.logged_get_count"
}
