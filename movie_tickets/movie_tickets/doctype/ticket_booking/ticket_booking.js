// Copyright (c) 2026, hardik and contributors
// For license information, please see license.txt

frappe.ui.form.on("Ticket Booking", {
    //show available seats,using frm.set_intro or frm.dashboard.set_headline.

    //On selecting a show, show alert if available_seats < 5: "Only {n} seats remaining!"
   show(frm) {

        frm.set_intro("");

        if (!frm.doc.show) return;

        const currentShow = frm.doc.show; // capture at call time

        frappe.db.get_value("Show", frm.doc.show, "available_seats").then(r => {
            // Discard response if user already changed show again
            if (frm.doc.show !== currentShow) return;

            frm.set_intro(""); // clear again right before setting new value

            if (r.message) {
                frm.set_intro(
                    "Available Seats: " + r.message.available_seats,
                    "blue"
                );
                if (r.message.available_seats < 5) {
                    frappe.msgprint(
                        `Only ${r.message.available_seats} seats remaining!`,
                        "Warning"
                    );
                }
            }

        });

    },

    
    refresh(frm) {
        calculate_total(frm);
        // Add custom button "Send Booking Confirmation" (visible after submit) that calls the send_booking_confirmation API.
        if (frm.doc.docstatus === 1) {
            if (!frm.custom_buttons["Send Booking Confirmation"]) {
                frm.add_custom_button("Send Booking Confirmation", () => {
                    frappe.call({
                        method: "movie_tickets.movie_tickets.api.send_booking_confirmation",
                        args: {
                            booking_name: frm.doc.name

                        },
                        callback: (r) => {
                            if (r.message) {
                                frappe.msgprint("Booking confirmation sent successfully.");
                            }
                        }
                    });
                });
            }
        }

    // Use frappe.confirm before cancellation with refund policy message.

    // Hide built-in Cancel button on submitted docs
    frm.page.btn_secondary.hide();

    // Show custom Cancel Booking only on submitted, non-cancelled docs
    if (frm.doc.docstatus === 1 && frm.doc.booking_status !== "Cancelled") {

        frm.add_custom_button("Cancel Booking", () => {

            const bookingDate  = frm.doc.show_date
                ? frappe.datetime.str_to_user(frm.doc.show_date)
                : "N/A";
            const totalAmount  = format_currency(frm.doc.total_amount, frm.doc.currency);
            const seats        = (frm.doc.seats || []).map(s => s.seat_label).join(", ") || "N/A";

            // Show refund policy based on your on_cancel logic
            frappe.confirm(
                `<div style="line-height:1.7;font-size:13px;">
                    <p><strong>Are you sure you want to cancel this booking?</strong></p>
                    <table style="width:100%;border-collapse:collapse;margin:10px 0;">
                        <tr>
                            <td style="padding:4px 0;color:var(--text-muted);width:50%;">Booking</td>
                            <td style="padding:4px 0;font-weight:500;">${frm.doc.name}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0;color:var(--text-muted);">Show Date</td>
                            <td style="padding:4px 0;font-weight:500;">${bookingDate}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0;color:var(--text-muted);">Seats</td>
                            <td style="padding:4px 0;font-weight:500;">${seats}</td>
                        </tr>
                        <tr>
                            <td style="padding:4px 0;color:var(--text-muted);">Amount Paid</td>
                            <td style="padding:4px 0;font-weight:500;">${totalAmount}</td>
                        </tr>
                    </table>
                    <div style="background:var(--alert-bg-warning);border-left:3px solid var(--yellow);
                                padding:10px 12px;border-radius:4px;margin-top:8px;font-size:12px;">
                        <strong>Refund Policy</strong><br>
                        • More than <strong>4 hours</strong> before show → <strong>100% refund</strong> (${totalAmount})<br>
                        • Between <strong>2–4 hours</strong> before show → <strong>50% refund</strong> (${format_currency(frm.doc.total_amount * 0.5, frm.doc.currency)})<br>
                        • Less than <strong>2 hours</strong> before show → <strong>No refund</strong><br>
                        • Refund will be processed within <strong>5–7 business days</strong>
                    </div>
                </div>`,

                () => {
                    // After confirm — prompt for cancellation reason
                    frappe.prompt(
                        {
                            fieldname: "cancellation_reason",
                            fieldtype: "Small Text",
                            label:     "Cancellation Reason",
                            reqd:      1
                        },
                        ({ cancellation_reason }) => {

                            frappe.call({
                                method:  "movie_tickets.movie_tickets.doctype.ticket_booking.ticket_booking.cancel_booking",
                                args: {
                                    name:                frm.doc.name,
                                    cancellation_reason: cancellation_reason
                                },
                                
                                callback(r) {
                                    if (!r.exc) {
                                        const refund = r.message?.refund || 0;
                                        frappe.show_alert({
                                            message: refund > 0
                                                ? `Booking cancelled. Refund of ${format_currency(refund, frm.doc.currency)} will be processed in 5–7 business days.`
                                                : "Booking cancelled. No refund applicable as per policy.",
                                            indicator: "orange"
                                        }, 6);
                                        window.location.reload(); // reload to reflect status change and update seat availability
                                    }
                                }
                            });

                        },
                        "Provide Cancellation Reason",
                        "Submit"
                    );
                }
            );

        }).css({
            "color":        "white",
            "background":   "#e74c3c",
            "border-color": "#e74c3c"
        });
    }
            
        
        //• Add a custom button "Select Seats" that opens a dialog showing a visual seat grid (rows x cols from screen). 
    // Booked seats shown as disabled/red, available as green/clickable. On confirm, populate the Booked Seat child table.
        if (!frm.custom_buttons["Select Seats"] && frm.doc.docstatus === 0 && frm.is_new()) {
            frm.add_custom_button("Select Seats", () => {
                if (!frm.doc.show) {
                    frappe.msgprint({ message: "Please select a show first.", title: "Error", indicator: "red" });
                    return;
                }

                const d = new frappe.ui.Dialog({
                    title: "Select Seats",
                    fields: [
                        {
                            fieldname: "seat_selection",
                            fieldtype: "HTML",
                            options: "<div id='seat-grid' style='padding:10px;'>Loading seats...</div>"
                        }
                    ],
                    primary_action_label: "Confirm",
                    primary_action() {
                        const selectedEls = d.$wrapper.find("#seat-grid .seat.selected"); // only .selected seats

                        if (!selectedEls.length) {
                            frappe.msgprint({ message: "Please select at least one seat.", indicator: "orange" });
                            return;
                        }

                        const pricePerSeat = frm.doc.price_per_seat || 0;

                        frm.clear_table("seats"); // clear existing selections - can be optimized to preserve unchanged seats
                        selectedEls.each(function () { // regular function to access `this`
                            const el  = $(this); // jQuery wrapper for clicked element
                            const row = frm.add_child("seats"); // add a new row to the child table
                            row.seat_label  = el.data("seat-label"); // e.g. "A-5"
                            row.row_letter  = el.data("row-letter"); // e.g. "A"
                            row.seat_number = el.data("seat-number"); // e.g. 5
                            row.seat_price  = pricePerSeat;
                        });

                        frm.set_value("number_of_seats", selectedEls.length); // update number_of_seats based on selection
                        frm.set_value("total_amount", selectedEls.length * pricePerSeat); // update total_amount
                        frm.refresh_field("seats"); // refresh the child table to show new rows

                        d.hide(); // close the dialog after confirming selection
                    }
                });

                d.show();

                // Step 1: Fetch Show doc
                frappe.db.get_doc("Show", frm.doc.show).then(showDoc => {

                    // Step 2: Fetch Screen doc for grid dimensions
                    frappe.db.get_doc("Screen", showDoc.screen).then(screenDoc => {
                        const rows = screenDoc.seat_rows;
                        const cols = screenDoc.seats_per_row;

                        // Step 3: Fetch all submitted, pending non-cancelled Ticket Bookings for this show
                        // Then read their `seats` child table directly from the doc — no get_list on child
                        frappe.db.get_list("Ticket Booking", {
                            filters: [
                                ["show",           "=",  frm.doc.show],
                                ["booking_status", "not in", ["Cancelled", "Expired"]],
                               
                            ],
                            fields: ["name"]
                        }).then(bookings => {

                            // Fetch each booking doc fully so we can read its seats child table
                            const docPromises = bookings
                                .filter(b => b.name !== frm.doc.name)   // exclude current doc
                                .map(b => frappe.db.get_doc("Ticket Booking", b.name));

                            Promise.all(docPromises).then(bookingDocs => {

                                // Collect all booked seat labels from other bookings
                                const bookedSeats = new Set();
                                bookingDocs.forEach(doc => {
                                    (doc.seats || []).forEach(s => {
                                        if (s.seat_label) bookedSeats.add(s.seat_label);
                                    });
                                });

                                // Seats already in the current booking (preserve on re-open)
                                const alreadySelected = new Set(
                                    (frm.doc.seats || []).map(s => s.seat_label)
                                );

                                // ── Resize dialog to fit the grid ──────────────────────
                                const cellSize    = 44;
                                const gap         = 6;
                                const gridWidth   = cols * cellSize + (cols - 1) * gap + 32;  // +32 padding
                                const gridHeight  = rows * cellSize + (rows - 1) * gap + 100; // +100 for legend
                                const dialogWidth = Math.max(400, Math.min(gridWidth, window.innerWidth - 80));

                                d.$wrapper.find(".modal-dialog").css({
                                    "max-width": dialogWidth + "px",
                                    "width":     dialogWidth + "px"
                                });
                                d.$wrapper.find(".modal-body").css({
                                    "max-height": (gridHeight + 120) + "px",
                                    "overflow-y": "auto"
                                });

                                // ── Build grid HTML ────────────────────────────────────
                                let html = `
                                    <div style="margin-bottom:12px;display:flex;gap:16px;flex-wrap:wrap;font-size:12px;color:var(--text-color);">
                                        <span><span style="display:inline-block;width:14px;height:14px;background:#4CAF50;border-radius:3px;margin-right:4px;vertical-align:middle;"></span>Available</span>
                                        <span><span style="display:inline-block;width:14px;height:14px;background:#FFD700;border-radius:3px;margin-right:4px;vertical-align:middle;"></span>Selected</span>
                                        <span><span style="display:inline-block;width:14px;height:14px;background:#ff4d4d;border-radius:3px;margin-right:4px;vertical-align:middle;"></span>Booked</span>
                                    </div>
                                    <div style="display:grid;grid-template-columns:repeat(${cols}, ${cellSize}px);gap:${gap}px;">
                                `;

                                for (let r = 0; r < rows; r++) {
                                    const rowLetter = String.fromCharCode(65 + r); // A, B, C...
                                    for (let c = 1; c <= cols; c++) {
                                        const seatLabel  = `${rowLetter}-${c}`;
                                        const isBooked   = bookedSeats.has(seatLabel);
                                        const isSelected = alreadySelected.has(seatLabel);

                                        const bg     = isBooked   ? "#ff4d4d"
                                                    : isSelected ? "#FFD700"
                                                    :              "#4CAF50";
                                        const cursor = isBooked ? "not-allowed" : "pointer";
                                        const cls    = `seat ${isBooked   ? "booked"
                                                            : isSelected ? "selected available"
                                                            :              "available"}`;

                                        html += `
                                            <div
                                                class="${cls}"
                                                data-seat-label="${seatLabel}"
                                                data-row-letter="${rowLetter}"
                                                data-seat-number="${c}"
                                                style="width:${cellSize}px;height:${cellSize}px;line-height:${cellSize}px;
                                                    text-align:center;font-size:11px;font-weight:600;
                                                    cursor:${cursor};background:${bg};
                                                    color:white;border-radius:5px;user-select:none;">
                                                ${seatLabel}
                                            </div>`;
                                    }
                                }

                                html += `</div>`;
                                d.$wrapper.find("#seat-grid").html(html);

                                // Delegated click — only on .available seats, scoped to dialog
                                d.$wrapper.find("#seat-grid").on("click", ".available", function () {
                                    const el = $(this);
                                    el.toggleClass("selected");
                                    el.css("background", el.hasClass("selected") ? "#FFD700" : "#4CAF50");
                                });

                            }).catch(err => {
                                console.error("Failed to fetch booking docs:", err);
                                d.$wrapper.find("#seat-grid").html("<p style='color:red;padding:10px;'>Failed to load booked seats.</p>");
                            });

                        }).catch(err => {
                            console.error("Failed to fetch ticket bookings:", err);
                            d.$wrapper.find("#seat-grid").html("<p style='color:red;padding:10px;'>Failed to fetch booking list.</p>");
                        });

                    }).catch(err => {
                        console.error("Failed to fetch screen doc:", err);
                        d.$wrapper.find("#seat-grid").html("<p style='color:red;padding:10px;'>Failed to load screen layout.</p>");
                    });

                }).catch(err => {
                    console.error("Failed to fetch show doc:", err);
                    d.$wrapper.find("#seat-grid").html("<p style='color:red;padding:10px;'>Failed to load show details.</p>");
                });
            });
        }
    }
});


frappe.ui.form.on("Booked Seat", {

    seats_add(frm) {
        calculate_total(frm);
    },

    seats_remove(frm) {
        calculate_total(frm);
    }

});

function calculate_total(frm) {

    let number_of_seats =
        frm.doc.seats ? frm.doc.seats.length : 0;

    let price_per_seat =
        frm.doc.price_per_seat || 0;

    frm.set_value(
        "number_of_seats",
        number_of_seats
    );

    frm.set_value(
        "total_amount",
        number_of_seats * price_per_seat
    );

}