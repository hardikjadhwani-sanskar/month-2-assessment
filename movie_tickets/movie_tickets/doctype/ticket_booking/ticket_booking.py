# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
from frappe.utils import getdate
from frappe.utils.data import get_datetime
from frappe.permissions import has_permission


class TicketBooking(Document):
	

	def validate(self):
		#• Check that the show’s show_status is Scheduled or Now Playing. 
		# If not, throw: "Cannot book tickets for a {show_status} show."
		show_doc = frappe.get_doc("Show", self.show)
		if show_doc.show_status not in ["Scheduled", "Now Playing"]:
			frappe.throw(f"Cannot book tickets for a {show_doc.show_status} show.")


		#• Validate each seat in the child table is available by querying existing confirmed/pending bookings for the same show. 
		# If any seat is taken, throw: "Seat {seat_label} is already booked for this show."

		for seat in self.seats:
			booking = frappe.get_all(
				"Ticket Booking",
				filters={
					"name": ["!=", self.name],
					"show": self.show,
					"booking_status": ["in", ["Pending", "Confirmed"]],
					"seat_label": seat.seat_label
				}
			)
			if booking:
				frappe.throw(f"Seat {seat.seat_label} is already booked for this show.")

		# • Validate no duplicate seats within the same booking.
		seat_labels = [seat.seat_label for seat in self.seats]
		if len(seat_labels) != len(set(seat_labels)):
			frappe.throw("Duplicate seats found in the booking.")

		#number_of_seats (Int, read_only — auto-calculated from child table count -seats ),
		self.number_of_seats = len(self.seats)
		
		#number_of_seats * price_per_seat

		self.total_amount = self.number_of_seats * self.price_per_seat


		#• Validate number_of_seats >= 1 and <= 10 (max 10 tickets per booking).
		if self.number_of_seats < 1 or self.number_of_seats > 10:
			frappe.throw("You can book between 1 and 10 tickets per booking.")

		#• Validate seat_label format: "{ROW_LETTER}-{SEAT_NUMBER}" (e.g., "A-12"). 
		# Row letter must be within screen’s seat_rows range, seat number within seats_per_row.

		for seat in self.seats:
			if not self.validate_seat_label(seat.seat_label):
				frappe.throw(f"Invalid seat label format: {seat.seat_label}. Expected format: ROW-SEAT (e.g., A-12).")

	def validate_seat_label(self, seat_label):
		parts = seat_label.split("-")
		if len(parts) != 2:
			return False

		row_letter, seat_number_str = parts
		if not row_letter.isalpha() or not seat_number_str.isdigit():
			return False

		row_letter = row_letter.upper()
		seat_number = int(seat_number_str)

		show_doc = frappe.get_doc("Show", self.show)
		screen_doc = frappe.get_doc("Screen", show_doc.screen)

		max_row_letter = chr(ord('A') + screen_doc.seat_rows - 1) #Calculate max row letter based on seat_rows (e.g., 5 rows → 'E')
		if row_letter < 'A' or row_letter > max_row_letter: 
			return False

		if seat_number < 1 or seat_number > screen_doc.seats_per_row:
			return False

		return True
		
	def before_save(self):
		# decrement available_seats in Show and increment booked_seats in Show even on pending bookings to prevent overbooking in concurrent scenarios.
		if self.booking_status == "Pending":
			show_doc = frappe.get_doc("Show", self.show)
			show_doc.booked_seats += self.number_of_seats
			show_doc.available_seats -= self.number_of_seats
			frappe.db.set_value("Show", self.show, {
				"booked_seats": show_doc.booked_seats,
				"available_seats": show_doc.available_seats
			})
			frappe.db.commit()
	
	def on_submit(self):
		#Set booking_status to Confirmed and payment_status to Paid.
		self.db_set("booking_status", "Confirmed")
		self.db_set("payment_status", "Paid")

		#Update Show: increment booked_seats, decrement available_seats.
		show_doc = frappe.get_doc("Show", self.show)
		show_doc.booked_seats += self.number_of_seats
		show_doc.available_seats -= self.number_of_seats
		frappe.db.set_value("Show", self.show, {
			"booked_seats": show_doc.booked_seats,
			"available_seats": show_doc.available_seats
		})
		frappe.db.commit()
		

	def on_cancel(self):
		# Calculate refund based on cancellation window
		show_doc = frappe.get_doc("Show", self.show)
		show_datetime = get_datetime(f"{show_doc.show_date} {show_doc.start_time}")
		time_diff = show_datetime - datetime.datetime.now()

		if time_diff > datetime.timedelta(hours=4):
			refund_amount  = self.total_amount
			payment_status = "Refunded"
		elif time_diff > datetime.timedelta(hours=2):
			refund_amount  = self.total_amount * 0.5
			payment_status = "Refunded"
		else:
			refund_amount  = 0
			payment_status = self.payment_status  # unchanged

		# Use db_set for all field updates — never self.save() inside on_cancel
		self.db_set("booking_status",      "Cancelled",                update_modified=False)
		self.db_set("refund_amount",       refund_amount,              update_modified=False)
		self.db_set("payment_status",      payment_status,             update_modified=False)
		self.db_set("cancellation_time",   frappe.utils.now_datetime(), update_modified=False)
		self.db_set("cancellation_reason", self.cancellation_reason or "", update_modified=False)

		# Update Show counters safely
		frappe.db.set_value("Show", self.show, {
			"booked_seats":    max((show_doc.booked_seats    or 0) - (self.number_of_seats or 0), 0),
			"available_seats": (show_doc.available_seats or 0) + (self.number_of_seats or 0)
		})
		# No frappe.db.commit() — Frappe handles the transaction automatically
			
		


	

@frappe.whitelist()
def cancel_booking(name, cancellation_reason):
    doc = frappe.get_doc("Ticket Booking", name)

    if doc.docstatus != 1:
        frappe.throw(_("Only submitted bookings can be cancelled."))

    if doc.booking_status == "Cancelled":
        frappe.throw(_("This booking is already cancelled."))

    # Set cancellation_reason before cancel() so on_cancel can access it via self
    doc.cancellation_reason = cancellation_reason

    # This triggers on_cancel automatically — your hook handles everything else
    doc.cancel()

    return { "refund": doc.refund_amount }


def has_permission(doc, user=None, permission_type=None):

    user = user or frappe.session.user

    # System Manager gets full access
    if "System Manager" in frappe.get_roles(user):
        return True

    # Cinema Manager full access
    if "Cinema Manager" in frappe.get_roles(user):
        return True

    # Customer can only see own bookings
    if "Customer" in frappe.get_roles(user):

        return doc.booked_by == user

    return False

def get_permission_query_conditions(user):

    if not user:
        user = frappe.session.user

    roles = frappe.get_roles(user)

    if (
        "System Manager" in roles or
        "Cinema Manager" in roles
    ):
        return ""

    if "Customer" in roles:

        return f"""
            `tabTicket Booking`.booked_by =
            {frappe.db.escape(user)}
        """

    return "1=0"



