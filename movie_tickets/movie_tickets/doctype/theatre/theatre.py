# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Theatre(Document):
	
	# autoname with theatre_name - city like PVR - Ahmedabad
	def autoname(self):
		self.name = f"{self.theatre_name} - {self.city}"