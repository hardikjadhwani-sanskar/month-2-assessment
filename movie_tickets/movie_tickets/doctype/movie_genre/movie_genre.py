# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MovieGenre(Document):
	#Validate no duplicate genre_name (case-insensitive check).
	def validate(self):
		if not self.genre_name:
			frappe.throw("Genre Name is required")
		if frappe.db.exists("Movie Genre", {"genre_name": self.genre_name, "name": ["!=", self.name]}): 
			frappe.throw("A movie genre with this name already exists")