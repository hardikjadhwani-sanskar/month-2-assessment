// movie_tickets/public/js/cinema.js

(function () {
    "use strict";

    // ── App loaded confirmation ───────────────────────────────────────────
    console.log(
        "%c🎬 Movie Tickets App Loaded",
        "color:#1a1a2e;font-weight:bold;font-size:14px;"
    );

    // ── Ctrl+Shift+B → Open New Ticket Booking form ──────────────────────
    document.addEventListener("keydown", function (e) {
        if (e.ctrlKey && e.shiftKey && e.key === "B") {
            e.preventDefault();

            // Only works inside the Frappe desk
            if (typeof frappe !== "undefined" && frappe.set_route) {
                frappe.set_route("Form", "Ticket Booking", "new-ticket-booking-1");
                frappe.show_alert({
                    message: "Opening New Ticket Booking...",
                    indicator: "blue"
                }, 3);
            }
        }
    });

    // ── Apply booking status badge classes to list/form views ────────────
    frappe.after_ajax(function () {
        apply_status_badges();
    });

    function apply_status_badges() {
        // Map Frappe's indicator text to our CSS badge classes
        const statusMap = {
            "Pending":   "badge-pending",
            "Confirmed": "badge-confirmed",
            "Cancelled": "badge-cancelled",
            "Expired":   "badge-expired"
        };

        $(".indicator").each(function () {
            const text = $(this).text().trim();
            if (statusMap[text]) {
                $(this)
                    .addClass("booking-status-badge " + statusMap[text])
                    .removeClass("indicator");
            }
        });
    }

    // ── Houseful helper — call from form JS when available_seats = 0 ─────
    window.CinemaUtils = {

        /**
         * Renders a houseful badge next to a given jQuery element.
         * Usage in form JS: CinemaUtils.showHouseful(frm.$wrapper.find(".form-page"))
         */
        showHouseful(target) {
            if (!target.find(".houseful-indicator").length) {
                target.prepend(
                    `<div class="houseful-indicator" style="margin-bottom:12px;">
                        Houseful
                    </div>`
                );
            }
        },

        removeHouseful(target) {
            target.find(".houseful-indicator").remove();
        },

        /**
         * Updates a seat availability progress bar element.
         * Usage: CinemaUtils.updateAvailabilityBar(el, available, total)
         */
        updateAvailabilityBar(barEl, available, total) {
            if (!total) return;
            const pct      = (available / total) * 100;
            const fillClass = pct > 50 ? "fill-high"
                            : pct > 20 ? "fill-medium"
                            :             "fill-low";

            barEl.find(".seat-availability-fill")
                .css("width", pct + "%")
                .removeClass("fill-high fill-medium fill-low")
                .addClass(fillClass);
        }
    };

})();