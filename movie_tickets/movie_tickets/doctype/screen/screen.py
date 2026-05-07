# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class Screen(Document):
	#Naming: By theatre + screen_name
    
	def autoname(self):
		
		self.name = f"{self.theatre} - {self.screen_name}"


	#Validate that total_seats = seat_rows * seats_per_row. If mismatch, throw error.
	def validate(self):
		expected_total = self.seat_rows * self.seats_per_row
		if self.total_seats != expected_total:
			frappe.throw(f"Total Seats should be equal to Seat Rows x Seats Per Row ({expected_total})")

	def after_insert(self):
		theatre_doc = frappe.get_doc("Theatre", self.theatre)
		theatre_doc.total_screens += 1
		theatre_doc.save()
		frappe.logger().info(theatre_doc.total_screens)