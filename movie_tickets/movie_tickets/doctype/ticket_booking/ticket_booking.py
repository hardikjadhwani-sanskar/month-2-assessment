# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class TicketBooking(Document):
	

	def before_save(self):

		#number_of_seats (Int, read_only — auto-calculated from child table count -seats ),
		self.number_of_seats = len(self.seats)
		
		#number_of_seats * price_per_seat

		self.total_amount = self.number_of_seats * self.price_per_seat
