// Copyright (c) 2026, hardik and contributors
// For license information, please see license.txt


// • Indicators: Green = Now Showing, Blue = Upcoming, Gray = Ended.
// • Default columns: title, language, genre, rating, release_date, movie_status.

frappe.ui.form.on("Movie", {
	refresh(frm) {
        const today = frappe.datetime.get_today();
        if (frm.doc.release_date > today) {
            frm.set_indicator("movie_status", "Upcoming", "blue");
        } else if (frm.doc.release_date <= today) {
            frm.set_indicator("movie_status", "Now Showing", "green");
        } else {
            frm.set_indicator("movie_status", "Ended", "gray");
        }
        
	},
});
