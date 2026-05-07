// Copyright (c) 2026, hardik and contributors
// For license information, please see license.txt


// • On selecting a screen, auto-fetch and set ticket_price from screen.base_price using frappe.db.get_value.
// • On selecting a movie, fetch duration and show calculated end_time as a message.
// • Add custom button "View Bookings" → navigates to Ticket Booking list filtered by show.
// • Dashboard indicators: booked (Blue), available (Green), occupancy % (Orange if > 80%, Red if 100%).
// Indicators: Green = Scheduled, Orange = Now Playing, Gray = Completed, Red = Cancelled.
frappe.ui.form.on("Show", {

    
    
	refresh(frm) {

        // • On selecting a screen, auto-fetch and set ticket_price from screen.base_price using frappe.db.get_value.
        frappe.db.get_value("Screen", frm.doc.screen, "base_price").then(r => {
            if (r.message) {
                frm.set_value("ticket_price", r.message.base_price);
            }
        });


      

         // • Add custom button "View Bookings" → navigates to Ticket Booking list filtered by show.
        if (frm.doc.name) {
            frm.add_custom_button("View Bookings", () => {
                frappe.set_route("List", "Ticket Booking", { show: frm.doc.name });
            });
        }

         // • Dashboard indicators: booked (Blue), available (Green), occupancy % (Orange if > 80%, Red if 100%).
        const booked = frm.doc.booked_seats || 0;
        const available = frm.doc.available_seats || 0;
        const total = booked + available;
        const occupancy = total > 0 ? (booked / total) * 100 : 0;

        frm.dashboard.add_indicator(`Booked: ${booked}`, "blue");
        frm.dashboard.add_indicator(`Available: ${available}`, "green");
        if (occupancy >= 100) {
            frm.dashboard.add_indicator(`Occupancy: ${occupancy.toFixed(2)}%`, "red");
        } else if (occupancy > 80) {
            frm.dashboard.add_indicator(`Occupancy: ${occupancy.toFixed(2)}%`, "orange");
        } else {
            frm.dashboard.add_indicator(`Occupancy: ${occupancy.toFixed(2)}%`, "green");
        }

	},



    movie(frm) {

        if (
            !frm.doc.movie ||
            !frm.doc.start_time
        ) {
            return;
        }

        frappe.db.get_value(
            "Movie",
            frm.doc.movie,
            "duration_minutes"
        ).then(r => {

            if (r.message) {

                const duration =
                    r.message.duration_minutes;

                let start =
                    moment(
                        frm.doc.start_time,
                        "HH:mm:ss"
                    );

                let end_time =
                    start.add(duration, "minutes")
                    .format("HH:mm:ss");

                frm.set_value(
                    "end_time",
                    end_time
                );

                frappe.msgprint(
                    `
                    Movie Duration:
                    ${duration} minutes

                    Estimated End Time:
                    ${end_time}
                    `
                );

            }

        });

    }
});

