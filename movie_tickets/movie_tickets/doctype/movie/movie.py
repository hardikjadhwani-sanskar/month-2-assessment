
import re
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Movie(Document):
   

    def before_save(self):
        self._generate_slug()
        self._compute_movie_status()

    def validate(self):
        self._validate_end_date()
        self._validate_duration_minutes()

    
    def _generate_slug(self):
        """Auto-generate a URL-friendly slug from the movie title.

        Example: "The Dark Knight" → "the-dark-knight"
        The slug is regenerated every time the title changes so it stays
        in sync, while remaining read-only from the UI.
        """
        if not self.title:
            return

        slug = self.title.lower().strip()

        # Replace any character that is not alphanumeric or whitespace with a space
        slug = re.sub(r"[^\w\s-]", "", slug)

        # Collapse multiple whitespace / hyphens into a single hyphen
        slug = re.sub(r"[\s_-]+", "-", slug)

        # Remove leading / trailing hyphens
        slug = slug.strip("-")

        self.slug = slug
    def _compute_movie_status(self):
        """Derive movie_status from release_date, end_date, and today's date.

        Rules:
          - No release_date          → Upcoming
          - today < release_date     → Upcoming
          - release_date ≤ today and (no end_date or today ≤ end_date) → Now Showing
          - end_date is set and today > end_date → Ended
        """
        if not self.release_date:
            self.movie_status = "Upcoming"
            return

        today_date = getdate(today())
        release = getdate(self.release_date)

        if today_date < release:
            self.movie_status = "Upcoming"
        elif self.end_date and today_date > getdate(self.end_date):
            self.movie_status = "Ended"
        else:
            self.movie_status = "Now Showing"

    def _validate_end_date(self):
        """Ensure end_date is strictly after release_date when both are set."""
        if self.end_date and self.release_date:
            if getdate(self.end_date) <= getdate(self.release_date):
                frappe.throw(
                    _("End Date must be after Release Date."),
                    title=_("Invalid Date Range"),
                )

    def _validate_duration_minutes(self):
        """Ensure duration_minutes is within the allowed range [1, 600]."""
        if self.duration_minutes is not None:
            if not (1 <= int(self.duration_minutes) <= 600):
                frappe.throw(
                    _("Duration must be between 1 and 600 minutes."),
                    title=_("Invalid Duration"),
                )