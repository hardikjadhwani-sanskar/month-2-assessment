import frappe
import unittest
import datetime
from frappe.utils import now_datetime, getdate, today


# ─────────────────────────────────────────────────────────────────────────────
# Factories
# ─────────────────────────────────────────────────────────────────────────────

def make_theatre():
    """Creates a unique Theatre using a hash suffix to avoid name clashes."""
    doc = frappe.new_doc("Theatre")
    doc.theatre_name = f"Test Theatre {frappe.generate_hash(length=6)}"
    doc.city         = "Test City"
    doc.address      = "123 Test Street"
    doc.is_active    = 1
    doc.insert(ignore_permissions=True)
    return doc


def make_screen(theatre_name, rows=10, seats_per_row=10):
    """
    Creates a Screen under the given theatre.
    Uses a hash suffix so every call produces a unique screen name
    and frappe.db.exists() checks are not needed.
    Screen naming in Frappe: autoname = "{theatre}-{screen_name}"
    so we must use doc.name (returned after insert) everywhere.
    """
    doc = frappe.new_doc("Screen")
    doc.screen_name   = f"Screen {frappe.generate_hash(length=4)}"
    doc.theatre       = theatre_name
    doc.screen_type   = "Standard"
    doc.seat_rows     = rows
    doc.seats_per_row = seats_per_row
    doc.total_seats   = rows * seats_per_row
    doc.base_price    = 200
    doc.is_active     = 1
    doc.insert(ignore_permissions=True)
    return doc


def make_genre():
    """Creates a unique Movie Genre."""
    doc = frappe.new_doc("Movie Genre")
    doc.genre_name = f"Genre {frappe.generate_hash(length=6)}"
    doc.is_active  = 1
    doc.insert(ignore_permissions=True)
    return doc


def make_movie(genre_name):
    """
    Creates a Movie with a unique title linked to the given genre.
    Genre must be created before calling this — passed as argument
    so there is no hidden dependency on existing site data.
    """
    doc = frappe.new_doc("Movie")
    doc.title            = f"Test Movie {frappe.generate_hash(length=6)}"
    doc.language         = "English"
    doc.genre            = genre_name
    doc.duration_minutes = 120
    doc.release_date     = today()
    doc.rating           = "UA"
    doc.insert(ignore_permissions=True)
    return doc


def make_show(
    movie_name,
    screen_name,
    theatre_name,
    show_date=None,
    start_hour=20,
    total_seats=100,
    available_seats=None,
    show_status="Scheduled"
):
    """
    Creates and inserts a Show document.
    Accepts actual docnames (strings) returned by factory functions
    so Link validation always passes.
    """
    doc = frappe.new_doc("Show")
    doc.naming_series   = "SHW-.YYYY.-.#####"
    doc.movie           = movie_name
    doc.screen          = screen_name
    doc.theatre         = theatre_name
    doc.show_date       = show_date or today()
    doc.start_time      = f"{str(start_hour).zfill(2)}:00:00"
    doc.total_seats     = total_seats
    doc.available_seats = available_seats if available_seats is not None else total_seats
    doc.booked_seats    = 0
    doc.ticket_price    = 200
    doc.show_status     = show_status
    doc.insert(ignore_permissions=True)
    return doc


def make_booking(show_doc, seats, customer_email=None):
    """
    Creates, inserts, and submits a Ticket Booking document.
    seats: list of dicts [{"seat_label": "A-1"}, ...]
    Uses a unique email per call to avoid duplicate customer conflicts.
    """
    if not customer_email:
        customer_email = f"test_{frappe.generate_hash(length=4)}@example.com"

    doc = frappe.new_doc("Ticket Booking")
    doc.naming_series        = "BKG-.YYYY.-.#####"
    doc.show                 = show_doc.name
    doc.customer_name        = "Test Customer"
    doc.customer_email       = customer_email
    doc.customer_phone       = "9876543210"
    doc.booking_status       = "Pending"
    doc.payment_status       = "Unpaid"
    doc.booking_time         = now_datetime()
    doc.number_of_seats      = len(seats)
    doc.price_per_seat       = show_doc.ticket_price
    doc.total_amount         = len(seats) * show_doc.ticket_price
    doc.booking_expiry_minutes = 15

    for s in seats:
        label      = s["seat_label"]          # e.g. "A-1"
        parts      = label.split("-")
        row_letter = parts[0]                  # "A"
        seat_num   = int(parts[1]) if len(parts) > 1 else 1   # 1

        doc.append("seats", {
            "seat_label":  label,
            "row_letter":  row_letter,
            "seat_number": seat_num,
            "seat_price":  show_doc.ticket_price
        })

    doc.insert(ignore_permissions=True)
    doc.submit()
    return doc


def build_seat_list(labels):
    """Helper: turn ["A-1","A-2"] into [{"seat_label":"A-1"}, ...]"""
    return [{"seat_label": lbl} for lbl in labels]


# ─────────────────────────────────────────────────────────────────────────────
# Test Suite
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketBooking(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """
        Runs once before all tests.
        Creates shared base records with unique names so they never
        clash with existing site data or other test runs.
        frappe.db.commit() is called so tearDown's rollback does NOT
        wipe these records — only each test's own writes are rolled back.
        """
        frappe.set_user("Administrator")

        # Order matters: theatre → screen, genre → movie
        cls.theatre = make_theatre()
        # cls.screen  = make_screen(cls.theatre.name, rows=10, seats_per_row=10)
        cls.genre   = make_genre()
        cls.movie   = make_movie(cls.genre.name)

        # Commit so tearDown rollbacks don't wipe these base records
        frappe.db.commit()

    def setUp(self):
        """
        Runs before each test.
        Creates a fresh show with 100 seats so every test starts clean.
        No rollback here — tearDown handles cleanup.
        """
        self.screen = make_screen(
        self.theatre.name,
        rows=10,
        seats_per_row=10
        )

        self.show = make_show(
            movie_name   = self.movie.name,
            screen_name  = self.screen.name,
            theatre_name = self.theatre.name,
            total_seats  = 100
        )

    def tearDown(self):
        """
        Rolls back all DB writes made during the test (insert/submit/cancel).
        Does NOT affect records committed in setUpClass.
        """
        frappe.db.rollback()

    # ── Test 1 ───────────────────────────────────────────────────────────────

    def test_booking_decreases_available_seats(self):
        """
        Booking 3 seats on a 100-seat show should result in
        available_seats=97 and booked_seats=3.
        """
        make_booking(self.show, build_seat_list(["A-1", "A-2", "A-3"]))

        show = frappe.get_doc("Show", self.show.name)

        self.assertEqual(
            show.available_seats, 97,
            f"Expected available_seats=97, got {show.available_seats}"
        )
        self.assertEqual(
            show.booked_seats, 3,
            f"Expected booked_seats=3, got {show.booked_seats}"
        )

    # ── Test 2 ───────────────────────────────────────────────────────────────

    def test_cannot_book_already_taken_seat(self):
        """
        Booking seat A-1 twice for the same show must raise ValidationError.
        The error message must mention A-1.
        """
        make_booking(self.show, build_seat_list(["A-1", "A-2"]))

        with self.assertRaises(frappe.ValidationError) as ctx:
            make_booking(self.show, build_seat_list(["A-1", "A-3"]))

        self.assertIn(
            "A-1", str(ctx.exception),
            "Error message should mention the conflicting seat label"
        )

    # ── Test 3 ───────────────────────────────────────────────────────────────

    def test_cannot_book_for_cancelled_show(self):
        """
        Booking seats on a Cancelled show must raise ValidationError
        mentioning the show status.
        """
        cancelled_screen = make_screen(
            self.theatre.name
        )
        cancelled_show = make_show(
            movie_name   = self.movie.name,
            screen_name  = cancelled_screen.name,
            theatre_name = self.theatre.name,
            show_status  = "Cancelled"
        )

        with self.assertRaises(frappe.ValidationError) as ctx:
            make_booking(cancelled_show, build_seat_list(["A-1"]))

        self.assertIn(
            "Cancelled", str(ctx.exception),
            "Error message should mention the show status"
        )

    # ── Test 4 ───────────────────────────────────────────────────────────────

    def test_max_seats_per_booking_limit(self):
        """
        Booking 11 seats in a single booking (exceeds max 10) must raise
        ValidationError mentioning the limit.
        """
        seats = build_seat_list([f"A-{i}" for i in range(1, 12)])

        with self.assertRaises(frappe.ValidationError) as ctx:
            make_booking(self.show, seats)

        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            "10" in error_msg or "maximum" in error_msg or "exceed" in error_msg,
            f"Error message should mention seat limit. Got: {ctx.exception}"
        )

    # ── Test 5 ───────────────────────────────────────────────────────────────

    def test_full_refund_on_early_cancellation(self):
        """
        Cancelling more than 4 hours before the show must give 100% refund.
        refund_amount must equal total_amount.
        """
        refund_screen = make_screen(
            self.theatre.name
        )
        
        show_time = now_datetime() + datetime.timedelta(hours=6)

        show = make_show(
            movie_name   = self.movie.name,
            screen_name  = refund_screen.name,
            theatre_name = self.theatre.name,
            show_date    = show_time.date(),
            start_hour   = show_time.hour
        )

        booking = make_booking(show, build_seat_list(["A-1", "A-2"]))
        booking.cancellation_reason = "Test early cancellation"
        booking.cancel()

        # Re-fetch from DB — db_set in on_cancel writes to DB not memory
        updated = frappe.get_doc("Ticket Booking", booking.name)

        self.assertEqual(
            float(updated.refund_amount),
            float(updated.total_amount),
            f"Expected full refund={updated.total_amount}, got {updated.refund_amount}"
        )
        self.assertEqual(updated.booking_status, "Cancelled")
        self.assertEqual(updated.docstatus, 2)

    # ── Test 6 ───────────────────────────────────────────────────────────────

    def test_partial_refund_on_late_cancellation(self):
        """
        Cancelling between 2 and 4 hours before the show must give 50% refund.
        """
        show_time = now_datetime() + datetime.timedelta(hours=3)

        show = make_show(
            movie_name   = self.movie.name,
            screen_name  = self.screen.name,
            theatre_name = self.theatre.name,
            show_date    = show_time.date(),
            start_hour   = show_time.hour
        )

        booking = make_booking(show, build_seat_list(["B-1", "B-2"]))
        booking.cancellation_reason = "Test late cancellation"
        booking.cancel()

        updated         = frappe.get_doc("Ticket Booking", booking.name)
        expected_refund = float(updated.total_amount) * 0.5

        self.assertAlmostEqual(
            float(updated.refund_amount),
            expected_refund,
            places=2,
            msg=f"Expected 50% refund={expected_refund}, got {updated.refund_amount}"
        )
        self.assertEqual(updated.booking_status, "Cancelled")

    # ── Test 7 ───────────────────────────────────────────────────────────────

    def test_no_refund_on_very_late_cancellation(self):
        """
        Cancelling less than 2 hours before the show must give 0 refund.
        """
        show_time = now_datetime() + datetime.timedelta(hours=1)

        show = make_show(
            movie_name   = self.movie.name,
            screen_name  = self.screen.name,
            theatre_name = self.theatre.name,
            show_date    = show_time.date(),
            start_hour   = show_time.hour
        )

        booking = make_booking(show, build_seat_list(["C-1", "C-2"]))
        booking.cancellation_reason = "Test very late cancellation"
        booking.cancel()

        updated = frappe.get_doc("Ticket Booking", booking.name)

        self.assertEqual(
            float(updated.refund_amount), 0,
            f"Expected 0 refund, got {updated.refund_amount}"
        )
        self.assertEqual(updated.booking_status, "Cancelled")

    # ── Test 8 ───────────────────────────────────────────────────────────────

    def test_show_conflict_validation(self):
        """
        Creating a show that overlaps an existing show on the same
        screen and date must raise ValidationError.

        Existing : 14:00 – 16:30
        Overlap  : 15:00 – 17:00
        """
        # Dedicated screen with unique name — never clashes with self.screen
        conflict_screen = make_screen(self.theatre.name, rows=5, seats_per_row=5)
        show_date = today()

        # First show 14:00–16:30 — must insert fine
        first_show = frappe.new_doc("Show")
        first_show.naming_series   = "SHW-.YYYY.-.#####"
        first_show.movie           = self.movie.name
        first_show.screen          = conflict_screen.name
        first_show.theatre         = self.theatre.name
        first_show.show_date       = show_date
        first_show.start_time      = "14:00:00"
        first_show.end_time        = "16:30:00"
        first_show.total_seats     = conflict_screen.total_seats
        first_show.available_seats = conflict_screen.total_seats
        first_show.booked_seats    = 0
        first_show.ticket_price    = 200
        first_show.show_status     = "Scheduled"
        first_show.insert(ignore_permissions=True)

        # Overlapping show 15:00–17:00 — must raise ValidationError
        with self.assertRaises(frappe.ValidationError) as ctx:
            overlap = frappe.new_doc("Show")
            overlap.naming_series   = "SHW-.YYYY.-.#####"
            overlap.movie           = self.movie.name
            overlap.screen          = conflict_screen.name
            overlap.theatre         = self.theatre.name
            overlap.show_date       = show_date
            overlap.start_time      = "15:00:00"
            overlap.end_time        = "17:00:00"
            overlap.total_seats     = conflict_screen.total_seats
            overlap.available_seats = conflict_screen.total_seats
            overlap.booked_seats    = 0
            overlap.ticket_price    = 200
            overlap.show_status     = "Scheduled"
            overlap.insert(ignore_permissions=True)

        error_msg = str(ctx.exception).lower()
        self.assertTrue(
            "overlap" in error_msg
            or "conflict" in error_msg
            or "already" in error_msg
            or "scheduled" in error_msg,
            f"Error should mention schedule conflict. Got: {ctx.exception}"
        )

    # ── Test 9 ───────────────────────────────────────────────────────────────

    def test_cancel_restores_seats(self):
        """
        Book 4 seats, submit, then cancel.
        available_seats must return to original value, booked_seats to 0.
        """
        initial_available = frappe.db.get_value(
            "Show", self.show.name, "available_seats"
        )

        booking = make_booking(
            self.show,
            build_seat_list(["D-1", "D-2", "D-3", "D-4"])
        )

        # Mid-state — seats must be deducted
        mid_available = frappe.db.get_value("Show", self.show.name, "available_seats")
        self.assertEqual(
            mid_available,
            initial_available - 4,
            "Seats should be deducted after booking"
        )

        # Cancel
        booking.cancellation_reason = "Test seat restoration"
        booking.cancel()

        # Final state — seats fully restored
        final = frappe.get_doc("Show", self.show.name)

        self.assertEqual(
            final.available_seats,
            initial_available,
            f"Expected available_seats={initial_available}, got {final.available_seats}"
        )
        self.assertEqual(
            final.booked_seats, 0,
            f"Expected booked_seats=0, got {final.booked_seats}"
        )

        updated_booking = frappe.get_doc("Ticket Booking", booking.name)
        self.assertEqual(updated_booking.booking_status, "Cancelled")
        self.assertEqual(updated_booking.docstatus, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTicketBooking)
    unittest.TextTestRunner(verbosity=2).run(suite)