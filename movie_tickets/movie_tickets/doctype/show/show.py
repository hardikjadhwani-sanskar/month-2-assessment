# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime
from frappe.utils import getdate

class Show(Document):

	# Check for showtime conflicts: No other show on the same screen should overlap 
	# with this show’s time window (start_time to end_time) on the same show_date. 
	# If conflict found, throw: "Screen {screen} already has a show scheduled from 
	# {existing_start} to {existing_end} on {show_date}."

	def validate(self):

		if not self.screen or not self.show_date :
			return
		
		if not self.start_time:
			frappe.throw("Start Time is required to calculate End Time")

		movie_doc = frappe.get_doc("Movie", self.movie)
		duration_minutes = movie_doc.duration_minutes #(int)
		self.end_time = self.calculate_end_time(self.start_time, duration_minutes)

		current_start = self.convert_to_time(self.start_time)
		current_end = self.convert_to_time(self.end_time)

		existing_shows = frappe.get_all(
			"Show",
			filters={
				"screen": self.screen,
				"show_date": self.show_date,
				"name": ["!=", self.name]
			},
			fields=["name", "start_time", "end_time"]
		)

		for show in existing_shows:

			existing_start = self.convert_to_time(show["start_time"])
			existing_end = self.convert_to_time(show["end_time"])

			if (
				current_start < existing_end
				and current_end > existing_start
			):

				frappe.throw(
					f"Screen {self.screen} already has a show "
					f"scheduled from {existing_start} to "
					f"{existing_end} on {self.show_date}."
				)

		#Validate that show_date is not in the past (allow today).
		
		if getdate(self.show_date) < datetime.date.today():frappe.throw("Show Date cannot be in the past.")

		if movie_doc.movie_status == "Ended":
			frappe.throw("Cannot schedule a show for a movie that has ended.")



	
		

	def before_insert(self):
		# available_seats (Int, read_only — auto-calculated from total_seats on creation)
		self.available_seats = self.total_seats
		if not self.ticket_price and self.screen:
			self.ticket_price = frappe.db.get_value(
				"Screen",
				self.screen,
				"base_price"
			)

	#• If show_status changes to Cancelled, find all Pending/Confirmed bookings 
	# for this show and auto-cancel them with reason "Show Cancelled". 
	# Set refund_amount = total_amount for each and payment_status to Refunded.


	def on_update(self):

		if self.show_status == "Cancelled":

			bookings = frappe.get_all(
				"Ticket Booking",
				filters={
					"show": self.name,
					"booking_status": ["in", ["Pending", "Confirmed"]]
				},
				fields=["name", "total_amount"]
			)

			for booking in bookings:
				booking_doc = frappe.get_doc("Ticket Booking", booking["name"])
				booking_doc.booking_status = "Cancelled"
				booking_doc.cancellation_reason = "Show Cancelled"
				booking_doc.refund_amount = booking["total_amount"]
				booking_doc.payment_status = "Refunded"
				booking_doc.cancellation_time = datetime.datetime.now()
				booking_doc.save()

	def calculate_end_time(self, start_time, duration_minutes):
		start_time = datetime.datetime.strptime(
			start_time,
			"%H:%M:%S"
		).time()

		start_datetime = datetime.datetime.combine(
			datetime.date.today(),
			start_time
		)

		end_datetime = start_datetime + datetime.timedelta(
			minutes=duration_minutes
		)

		return end_datetime.time()
	
	def convert_to_time(self, value):

			if isinstance(value, datetime.timedelta):

				total_seconds = int(value.total_seconds())

				hours = total_seconds // 3600
				minutes = (total_seconds % 3600) // 60
				seconds = total_seconds % 60

				return datetime.time(hours, minutes, seconds)

			if isinstance(value, str):

				return datetime.datetime.strptime(
					value,
					"%H:%M:%S"
				).time()

			return value