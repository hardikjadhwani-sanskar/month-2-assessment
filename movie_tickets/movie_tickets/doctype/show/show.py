# Copyright (c) 2026, hardik and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import datetime

class Show(Document):

	# end_time (Time, read_only — auto-calculated from start_time + movie duration)
	def before_save(self):
		movie_doc = frappe.get_doc("Movie", self.movie)
		if not movie_doc:
			return

		if not self.start_time:
			frappe.throw("Start Time is required to calculate End Time")

		duration_minutes = movie_doc.duration_minutes #(int)
		self.end_time = self.calculate_end_time(self.start_time, duration_minutes)
		self.available_seats = self.total_seats

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