# 🎬 Movie Tickets — Frappe App

A complete movie ticket booking system built on the Frappe Framework (v16+).
Manages movies, theaters, screens, show scheduling, seat-based ticket booking,
payment tracking, and cancellation with refund logic.

---

## Table of Contents

1. [App Description](#app-description)
2. [Setup Instructions](#setup-instructions)
3. [DocType List](#doctype-list)
4. [Seat Booking Lifecycle](#seat-booking-lifecycle)
5. [API Documentation](#api-documentation)
6. [Background Jobs](#background-jobs)
7. [Hooks Configuration](#hooks-configuration)
8. [Role-Based Permissions](#role-based-permissions)
9. [Web Portal Pages](#web-portal-pages)
10. [Script Report](#script-report)
11. [Data Migration Patches](#data-migration-patches)
12. [Test Instructions](#test-instructions)
13. [Fixtures](#fixtures)
14. [Assumptions](#assumptions)
15. [Limitations](#limitations)

---

## App Description

**Movie Tickets** is a Frappe custom application that covers:

- Master data management (Movies, Genres, Theaters, Screens)
- Show scheduling with conflict detection
- Seat-based ticket booking with real-time availability
- Payment tracking and auto-expiry of unpaid bookings
- Cancellation with time-window based refund logic
- Role-based access control (Cinema Manager, Box Office Staff, Customer)
- Public-facing web portal for movie listing and booking
- Scheduled background jobs for status updates and revenue digests
- QR code generation on booking confirmation
- Script reports with revenue analytics

**App Name:** `movie_tickets`  
**Module:** Movie Tickets  
**Framework:** Frappe v16+  
**Python:** 3.14+  
**Database:** MariaDB 10.6+  
**Node.js:** v24+

---

## Setup Instructions

### 1. Prerequisites

```bash
# Ensure Frappe bench is installed
bench --version

# Required: Python 3.14+, Node.js v24+, MariaDB 10.6+
python3 --version
node --version
mysql --version
```

### 2. Initialize Bench

```bash
bench init cinema-bench --frappe-branch version-16
cd cinema-bench
```

### 3. Create Site

```bash
bench new-site cinema.localhost
bench use cinema.localhost
```

### 4. Create and Install App

```bash
bench new-app movie_tickets
# Fill in: App Title = Movie Tickets, Module = Movie Tickets

bench --site cinema.localhost install-app movie_tickets
```

### 5. Install Python Dependencies

```bash
# QR code generation
bench pip install qrcode[pil]
```

### 6. Run Migrations and Build

```bash
bench --site cinema.localhost migrate
bench build --app movie_tickets
bench restart
```

### 7. Enable Scheduler

```bash
bench --site cinema.localhost scheduler enable
bench restart
```

### 8. Start Development Server

```bash
bench start
```

### 9. Enter Sample Data

After setup, enter sample data in this order (to satisfy foreign key dependencies):

```
1. Movie Genre     (6+ records)
2. Movie           (5+ records)
3. Theater         (3+ records)
4. Screen          (6+ records)
5. Show            (8+ records)
6. Ticket Booking  (4+ records)
7. Booking Configuration (1 record — Single DocType)
```

### 10. Restore Fixtures

```bash
bench --site cinema.localhost migrate
# Fixtures are auto-applied on migrate if registered in hooks.py
```

---

## DocType List

| # | DocType | Type | Module | Description |
|---|---|---|---|---|
| 1 | Movie Genre | Master | Movie Tickets | Genre classification for movies |
| 2 | Movie | Master | Movie Tickets | Movie master with status lifecycle |
| 3 | Theatre | Master | Movie Tickets | Theater with location and screen count |
| 4 | Screen | Master | Movie Tickets | Screen within a theater with seat config |
| 5 | Show | Transactional | Movie Tickets | Scheduled movie screening on a screen |
| 6 | Ticket Booking | Transactional (Submittable) | Movie Tickets | Customer booking with seat selection |
| 7 | Booked Seat | Child Table | Movie Tickets | Individual seat within a booking |
| 8 | Booking Configuration | Single | Movie Tickets | App-wide booking settings |

### Field Summary

#### Movie Genre
| Field | Type | Notes |
|---|---|---|
| genre_name | Data | Mandatory, Unique |
| description | Small Text | |
| is_active | Check | Default 1 |

#### Movie
| Field | Type | Notes |
|---|---|---|
| title | Data | Mandatory |
| slug | Data | Read Only, auto-generated |
| language | Select | English/Hindi/Gujarati/Tamil/Telugu/Other |
| genre | Link → Movie Genre | Mandatory |
| duration_minutes | Int | 1–600 |
| release_date | Date | Mandatory |
| end_date | Date | Must be > release_date |
| rating | Select | U/UA/A/S, default UA |
| movie_status | Select | Upcoming/Now Showing/Ended, Read Only |
| poster | Attach Image | |
| trailer_url | Data | |

#### Screen
| Field | Type | Notes |
|---|---|---|
| screen_name | Data | Mandatory |
| theater | Link → Theater | Mandatory |
| screen_type | Select | Standard/IMAX/3D/4DX |
| total_seats | Int | Must equal seat_rows × seats_per_row |
| seat_rows | Int | Mandatory |
| seats_per_row | Int | Mandatory |
| base_price | Currency | Mandatory |

#### Show
| Field | Type | Notes |
|---|---|---|
| movie | Link → Movie | Mandatory |
| screen | Link → Screen | Mandatory |
| theater | Link → Theater | Read Only, fetched |
| show_date | Date | Mandatory, not in past |
| start_time | Time | Mandatory |
| end_time | Time | Read Only, auto-calculated |
| total_seats | Int | Fetched from Screen |
| available_seats | Int | Read Only |
| booked_seats | Int | Read Only, default 0 |
| show_status | Select | Scheduled/Now Playing/Completed/Cancelled |
| ticket_price | Currency | Defaults from screen.base_price |

#### Ticket Booking
| Field | Type | Notes |
|---|---|---|
| show | Link → Show | Mandatory |
| customer_name | Data | Mandatory |
| customer_email | Data | Mandatory |
| customer_phone | Data | Mandatory |
| seats | Table → Booked Seat | Child table |
| number_of_seats | Int | Read Only, auto-calculated |
| price_per_seat | Currency | Fetched from Show |
| total_amount | Currency | Read Only, computed |
| booking_status | Select | Pending/Confirmed/Cancelled/Expired |
| payment_status | Select | Unpaid/Paid/Refunded |
| booking_time | Datetime | Read Only, default Now |
| cancellation_time | Datetime | Read Only |
| refund_amount | Currency | Read Only |
| cancellation_reason | Small Text | |
| booking_source | Select | Counter/Website/App (Custom Field via Fixture) |
| qr_code_url | Data | Read Only, set after QR generation |

#### Booking Configuration (Single)
| Field | Default | Description |
|---|---|---|
| max_seats_per_booking | 10 | Max seats allowed per booking |
| booking_expiry_minutes | 15 | Minutes before unpaid booking expires |
| full_refund_hours | 4 | Hours before show for 100% refund |
| partial_refund_hours | 2 | Hours before show for 50% refund |
| partial_refund_pct | 50 | Partial refund percentage |
| enable_auto_expiry | 1 | Enable/disable auto-expiry job |
| booking_open_days_before | 7 | Days in advance booking opens |

---

## Seat Booking Lifecycle

```
Customer selects seats
        ↓
create_booking API called
        ↓
Server re-validates seat availability
        ↓
Ticket Booking inserted (docstatus=0, status=Pending, payment=Unpaid)
        ↓
after_insert fires:
  → Seats DEDUCTED from Show immediately
    (booked_seats +n, available_seats -n)
  → Email sent: "Complete payment within 15 minutes"
        ↓
  ┌─────────────────┬───────────────────────────┐
  │  Payment made   │   Payment NOT made         │
  │  within 15 min  │   after 15 min             │
  ↓                 ↓                            │
on_submit         auto_expire_unpaid_bookings     │
  → status=Confirmed  (runs every 5 min)         │
  → payment=Paid    → status=Expired             │
  → QR generated    → seats RESTORED             │
  → Email sent      → seats RESTORED             │
        ↓                                        │
Customer cancels (custom Cancel Booking button)  │
        ↓
on_cancel fires:
  → Refund calculated based on time to show:
    >4 hours  → 100% refund
    2–4 hours → 50% refund
    <2 hours  → 0% refund
  → booking_status = Cancelled
  → docstatus = 2
  → Seats RESTORED to Show
```

---

## API Documentation

All APIs are in `movie_tickets/movie_tickets/api.py`.

### A) `get_seat_availability`

```
GET /api/method/movie_tickets.movie_tickets.api.get_seat_availability
Auth: Required (logged in)
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| show_name | string | ✅ | Show document name (e.g. SHW-2026-00001) |

**Response:**

```json
{
  "message": {
    "show_name": "SHW-2026-00001",
    "total_rows": 10,
    "seats_per_row": 15,
    "total_seats": 150,
    "available_seats": 143,
    "booked_seats": 7,
    "seat_grid": [
      [
        { "seat_label": "A1", "status": "available" },
        { "seat_label": "A2", "status": "booked" }
      ]
    ]
  }
}
```

---

### B) `create_booking`

```
POST /api/method/movie_tickets.movie_tickets.api.create_booking
Auth: Required (no guest access)
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| show | string | ✅ | Show name |
| customer_name | string | ✅ | Full name |
| customer_email | string | ✅ | Email address |
| customer_phone | string | ✅ | Phone number |
| seats | JSON array | ✅ | `[{"seat_label": "A1"}, {"seat_label": "A2"}]` |

**Race Condition Handling:**  
`frappe.lock_doc("Show", show_name)` is called before seat validation.
This acquires a DB-level lock so concurrent requests cannot double-book the same seat.
The lock is always released in a `finally` block.

**Response:**

```json
{
  "message": {
    "success": true,
    "booking_name": "BKG-2026-00001",
    "total_amount": 1350.0,
    "seats_booked": ["A1", "A2", "A3"],
    "message": "Booking created. Complete payment within 15 minutes."
  }
}
```

---

### C) `get_shows_for_movie`

```
GET /api/method/movie_tickets.movie_tickets.api.get_shows_for_movie
Auth: None (guest access allowed)
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| movie | string | ✅ | Movie document name |
| city | string | ❌ | Filter by theater city |
| date | string | ❌ | Filter by show date (YYYY-MM-DD) |

**Response:**

```json
{
  "message": [
    {
      "show_name": "SHW-2026-00001",
      "movie_title": "Inception",
      "theatre": "PVR IMAX",
      "screen": "PVR IMAX-Screen 1",
      "screen_type": "IMAX",
      "show_date": "2026-05-10",
      "start_time": "18:00:00",
      "end_time": "20:28:00",
      "ticket_price": 450.0,
      "available_seats": 233,
      "show_status": "Scheduled"
    }
  ]
}
```

---

### D) `send_booking_confirmation`

```
POST /api/method/movie_tickets.movie_tickets.api.send_booking_confirmation
Auth: Required
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| booking_name | string | ✅ | Ticket Booking name (e.g. BKG-2026-00001) |

**Response:**

```json
{
  "message": {
    "success": true,
    "message": "Confirmation email sent to customer@example.com"
  }
}
```

---

### E) `get_revenue_summary`

```
GET /api/method/movie_tickets.movie_tickets.api.get_revenue_summary
Auth: Required
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| theater | string | ❌ | Filter by theater name |
| from_date | string | ❌ | Start date (YYYY-MM-DD) |
| to_date | string | ❌ | End date (YYYY-MM-DD) |

**Response:**

```json
{
  "message": {
    "total_bookings": 142,
    "total_revenue": 198450.0,
    "total_seats_sold": 310,
    "avg_occupancy_pct": 78.4,
    "top_movie": {
      "movie_title": "Inception",
      "revenue": 87500.0,
      "bookings": 63,
      "seats_sold": 140
    },
    "filters_applied": {
      "theater": null,
      "from_date": "2026-05-01",
      "to_date": "2026-05-31"
    }
  }
}
```

---

### F) `cancel_booking`

```
POST /api/method/movie_tickets.movie_tickets.doctype.ticket_booking.ticket_booking.cancel_booking
Auth: Required
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| name | string | ✅ | Ticket Booking name |
| cancellation_reason | string | ✅ | Reason for cancellation |

**Response:**

```json
{
  "message": {
    "refund": 900.0
  }
}
```

---

### G) `get_dashboard_data` (Dashboard Page)

```
GET /api/method/movie_tickets.movie_tickets.page.cinema_dashboard.cinema_dashboard.get_dashboard_data
Auth: Required (Cinema Manager / System Manager)
```

**Response:** Occupancy by theatre, 30-day revenue trend, bookings by time slot, top 5 movies.

---

### H) `create_shows_bulk` (Bulk Show Creator)

```
POST /api/method/movie_tickets.movie_tickets.bulk_show_creator.create_shows_bulk
Auth: Required
```

**Parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| movie | string | ✅ | Movie name |
| screens | JSON array | ✅ | `["Screen 1", "Screen 2"]` |
| date_from | string | ✅ | Start date |
| date_to | string | ✅ | End date |
| show_times | JSON array | ✅ | `["10:00", "14:00", "19:00"]` |
| ticket_price | float | ✅ | Price per ticket |

---

## Background Jobs

All jobs registered in `hooks.py` under `scheduler_events`.  
Implemented in `movie_tickets/movie_tickets/tasks.py`.

| Job | Schedule | Description |
|---|---|---|
| `auto_expire_unpaid_bookings` | Every 5 min (`*/5 * * * *`) | Expires Pending+Unpaid bookings older than `booking_expiry_minutes`. Restores seats. |
| `update_movie_status` | Daily | Recalculates Upcoming/Now Showing/Ended based on dates |
| `update_show_status` | Hourly | Sets Scheduled→Now Playing→Completed based on time |
| `send_daily_revenue_digest` | 11 PM daily (`0 23 * * *`) | Sends HTML revenue summary to Cinema Managers |

**Test jobs manually:**

```bash
bench --site cinema.localhost execute movie_tickets.movie_tickets.tasks.auto_expire_unpaid_bookings
bench --site cinema.localhost execute movie_tickets.movie_tickets.tasks.update_movie_status
bench --site cinema.localhost execute movie_tickets.movie_tickets.tasks.update_show_status
bench --site cinema.localhost execute movie_tickets.movie_tickets.tasks.send_daily_revenue_digest
```

---

## Hooks Configuration


### override_whitelisted_methods

`frappe.client.get_count` is wrapped with `logged_get_count` in `overrides.py`
for auditing and logging purposes. See inline comments in `hooks.py` for full
use-case documentation, risks, and alternatives.

### app_include_css / app_include_js

| File | Purpose |
|---|---|
| `public/css/cinema.css` | Booking status badge colors, houseful pulse animation, seat color coding |
| `public/js/cinema.js` | App load log, `Ctrl+Shift+B` shortcut to open new booking form |

After any change to public files:

```bash
bench build --app movie_tickets
bench restart
```

---

## Role-Based Permissions

| Role | Create | Read | Write | Submit | Cancel | Notes |
|---|---|---|---|---|---|---|
| Cinema Manager | ✅ | ✅ | ✅ | ✅ | ✅ | Full access all DocTypes |
| Box Office Staff | ✅ (Booking only) | ✅ | ✅ (Booking) | ✅ | ✅ (Booking) | Read-only on Movie/Show/Screen |
| Customer | ❌ | ✅ (own bookings) | ❌ | ❌ | ❌ | Portal only, own bookings via has_permission |

**Test Users:**

| Email | Role | Password |
|---|---|---|
| manager@test.com | Cinema Manager | sanskar |
| staff@test.com | Box Office Staff | sanskar |
| customer@test.com | Customer | sanskar |

**has_permission** is implemented on Ticket Booking so Customers can only
see bookings where `booked_by = frappe.session.user`.

---

## Web Portal Pages

| URL | Auth | Description |
|---|---|---|
| `/now_showing` | Guest | Card grid of Now Showing movies. Filter by genre/language. |
| `/movie_shows?movie=MOV-XXXXX` | Guest (view) / Login (book) | Shows for a movie grouped by theater and date |
| `/my_bookings` | Login required | Logged-in user's booking history with status badges |

---

## Script Report

**Name:** Box Office Collection Report  
**Location:** `movie_tickets/movie_tickets/report/box_office_collection_report/`

**Columns:**
- Movie Title, Genre, Language
- Total Shows, Total Bookings, Total Seats Sold
- Total Revenue, Avg Occupancy (%), Avg Ticket Price

**Filters:**
- Theater (Link)
- Date Range (from_date, to_date)
- Genre (Link)
- Language (Select)

**Charts:**
- Bar chart: Top 10 movies by revenue
- Pie chart: Revenue by screen type (Standard/IMAX/3D/4DX)

---

## Data Migration Patches

All patches are in `movie_tickets/patches/v1_0/` and registered in `patches.txt`.

| Patch | Description |
|---|---|
| `recalculate_show_seat_counts` | Resets Show seat counters from actual submitted bookings |
| `set_movie_slugs` | Generates slugs for all Movies with empty slug field |
| `populate_booking_source` | Sets `booking_source = Counter` for all pre-existing bookings |

**Run all patches:**

```bash
bench --site cinema.localhost migrate
```

**Run a single patch manually:**

```bash
bench --site cinema.localhost execute movie_tickets.patches.v1_0.recalculate_show_seat_counts
bench --site cinema.localhost execute movie_tickets.patches.v1_0.set_movie_slugs
bench --site cinema.localhost execute movie_tickets.patches.v1_0.populate_booking_source
```

**Verify:**

```bash
bench --site cinema.localhost console
>>> frappe.get_all("Patch Log", filters={"patch": ["like", "%v1_0%"]}, fields=["patch", "creation"])
```

---

## Test Instructions

Tests are in:
`movie_tickets/movie_tickets/doctype/ticket_booking/test_ticket_booking.py`

### Run All Tests

```bash
bench --site cinema.localhost run-tests \
    --app movie_tickets \
    --module movie_tickets.movie_tickets.doctype.ticket_booking.test_ticket_booking
```

### Run a Single Test

```bash
bench --site cinema.localhost run-tests \
    --app movie_tickets \
    --module movie_tickets.movie_tickets.doctype.ticket_booking.test_ticket_booking \
    --test test_booking_decreases_available_seats
```

### Test Coverage

| # | Test Name | What It Validates |
|---|---|---|
| 1 | `test_booking_decreases_available_seats` | Booking 3 seats → available=97, booked=3 |
| 2 | `test_cannot_book_already_taken_seat` | Duplicate seat raises ValidationError |
| 3 | `test_cannot_book_for_cancelled_show` | Cancelled show booking raises error |
| 4 | `test_max_seats_per_booking_limit` | 11 seats in one booking raises error |
| 5 | `test_full_refund_on_early_cancellation` | Cancel >4hr before show → 100% refund |
| 6 | `test_partial_refund_on_late_cancellation` | Cancel 2–4hr before show → 50% refund |
| 7 | `test_no_refund_on_very_late_cancellation` | Cancel <2hr before show → 0% refund |
| 8 | `test_show_conflict_validation` | Overlapping show on same screen raises error |
| 9 | `test_cancel_restores_seats` | Cancel booking → seats fully restored |

### Expected Output

```
test_booking_decreases_available_seats ... ok
test_cancel_restores_seats ... ok
test_cannot_book_already_taken_seat ... ok
test_cannot_book_for_cancelled_show ... ok
test_full_refund_on_early_cancellation ... ok
test_max_seats_per_booking_limit ... ok
test_no_refund_on_very_late_cancellation ... ok
test_partial_refund_on_late_cancellation ... ok
test_show_conflict_validation ... ok

Ran 9 tests in 12.345s
OK
```

---

## Fixtures

Custom fields and property setters are exported as fixtures.

**Registered in `hooks.py`:**

```python
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Movie Tickets"]]
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "=", "Movie Tickets"]]
    }
]
```

**Export fixtures:**

```bash
bench --site cinema.localhost export-fixtures --app movie_tickets
```

**Verify fixture file:**

```bash
cat apps/movie_tickets/movie_tickets/fixtures/custom_field.json
```

**Fixtures auto-apply on:**

```bash
bench --site cinema.localhost migrate
```

---
 
## Assumptions
 

1. **Seats deducted on insert (not submit):** Based on the payment flow requirement,
   seats are held immediately when a booking is created (Pending status) so no other
   customer can book the same seat during the 15-minute payment window.

2. **Refund thresholds are read from Booking Configuration** Single DocType, not hardcoded.
   Default values: full refund >4hr, partial (50%) 2–4hr, no refund <2hr.

3. **Email requires a configured outgoing email account** in Frappe (Tools → Email Account).
   For development, Gmail SMTP with App Password is recommended.
   
4. **Bulk show creator** has a hard limit of 500 shows per job to prevent runaway
   background tasks.
   
5. **The auto-expiry job** only expires bookings where `docstatus != 2` (not already cancelled).
   Expired bookings are NOT submitted/cancelled via Frappe's workflow — their status
   is updated directly via `db_set` to avoid triggering `on_cancel` refund logic
   (no refund is applicable for expired unpaid bookings).

---
 
## Limitations
 
1. **No online payment gateway integration.** Payment status is set manually or
   via the `on_submit` hook. A real implementation would integrate Razorpay/Stripe
   and only submit the booking after payment confirmation.
2. **No real-time seat updates.** If two users open the seat map simultaneously,
   both will see the same seats as available. `frappe.lock_doc` prevents
   double-booking at the API level, but the UI does not update in real-time
   (no WebSocket push). In production, Socket.IO would be used.
3. **Maximum 26 rows per screen** (A–Z). Screens with more than 26 rows
   are not supported by the current row-letter generation (`chr(65 + r)`).
4. **QR code attached as a file** — not embedded inline in the ticket PDF.
   The print format references the file URL which requires the site to be
   accessible for the image to render when printing offline.
5. **Bulk show creator limit of 500 shows** per job. Very large date ranges
   with many screens and time slots must be broken into smaller batches.
6. **has_permission** for the Customer role uses `booked_by = current user`.
   Bookings created by Box Office Staff on behalf of a customer will not be
   visible to that customer's portal login unless `customer_email` matching
   is also implemented.
7. **No seat map on the web portal.** The interactive seat selection dialog
   is only available in the Frappe Desk (admin) interface. The web portal
   `Book Now` flow does not include a visual seat picker.
8. **Email delivery depends on outgoing email configuration.** If no outgoing
   email account is set up, `after_insert` and `on_submit` emails will silently
   fail with an `OutgoingEmailError`. Add try/except around all `frappe.sendmail`
   calls in production.
9. **The Dashboard page** requires Cinema Manager or System Manager role.
   Non-manager users who navigate to `/cinema-dashboard` will see a blank page.

---