frappe.query_reports["Box Office Collection Report"] = {

    filters: [
        {
            fieldname: "theatre",
            label:     __("Theatre"),
            fieldtype: "Link",
            options:   "Theatre",
            width:     200,
        },
        {
            fieldname: "from_date",
            label:     __("From Date"),
            fieldtype: "Date",
            default:   frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd:      0,
        },
        {
            fieldname: "to_date",
            label:     __("To Date"),
            fieldtype: "Date",
            default:   frappe.datetime.get_today(),
            reqd:      0,
        },
        {
            fieldname: "genre",
            label:     __("Genre"),
            fieldtype: "Link",
            options:   "Movie Genre",
        },
        {
            fieldname: "language",
            label:     __("Language"),
            fieldtype: "Select",
            options:   "\nEnglish\nHindi\nGujarati\nTamil\nTelugu\nOther",
        },
    ],

    // // ── Correct Frappe hook: fires after report data renders ──
    // after_refresh() {
    //     setTimeout(() => render_pie_chart(), 800);
    // },
};


function render_pie_chart() {
    const filters = frappe.query_report.get_values();

    // ── Fix: single method key, correct dotted path ──
    frappe.call({
        method: "movie_tickets.movie_tickets.report.box_office_collection_report.box_office_collection_report.get_pie_chart_ajax",
        args:   { filters: JSON.stringify(filters || {}) },

        callback(r) {
            if (!r.message || !r.message.length) return;

            const labels = r.message.map(d => d.screen_type || "Standard");
            const values = r.message.map(d => parseFloat(d.revenue)  || 0);

            // Remove old chart if re-rendering after filter change
            const existing = document.getElementById("box-office-pie-wrap");
            if (existing) existing.remove();

            // Create wrapper
            const wrap = document.createElement("div");
            wrap.id = "box-office-pie-wrap";
            wrap.style.cssText = [
                "margin: 24px 0",
                "padding: 20px",
                "background: var(--fg-color, #fff)",
                "border: 1px solid var(--border-color)",
                "border-radius: 8px",
            ].join(";");

            const title = document.createElement("h6");
            title.textContent = __("Revenue by Screen Type");
            title.style.cssText = "margin: 0 0 16px 0; font-weight: 600; font-size: 14px;";
            wrap.appendChild(title);

            const chartDiv = document.createElement("div");
            chartDiv.id = "pie-chart-container";
            wrap.appendChild(chartDiv);

            // Insert below the bar chart
            const reportChart = document.querySelector(
                ".chart-wrapper, .frappe-chart-wrapper, .report-chart-wrapper"
            );
            if (reportChart && reportChart.parentNode) {
                reportChart.parentNode.insertBefore(wrap, reportChart.nextSibling);
            } else {
                // Fallback: append to report area
                const reportArea = document.querySelector(
                    ".page-content .layout-main, .page-content"
                );
                if (reportArea) reportArea.appendChild(wrap);
            }

            // ── Fix: correct Frappe Charts constructor ──
            if (typeof frappe.Chart !== "undefined") {
                new frappe.Chart("#pie-chart-container", {
                    type:   "pie",
                    height: 280,
                    colors: ["#e8b84b", "#7fcfff", "#b87fff", "#4ade80", "#f87171"],
                    data: {
                        labels:   labels,
                        datasets: [{ values }],
                    },
                });
            } else {
                // Frappe Charts not available — render a simple HTML table fallback
                const total = values.reduce((a, b) => a + b, 0);
                let html = `<table class="table table-bordered" style="font-size:13px">
                    <thead><tr>
                        <th>${__("Screen Type")}</th>
                        <th>${__("Revenue")}</th>
                        <th>${__("Share %")}</th>
                    </tr></thead><tbody>`;

                labels.forEach((label, i) => {
                    const pct = total > 0 ? ((values[i] / total) * 100).toFixed(1) : 0;
                    html += `<tr>
                        <td>${label}</td>
                        <td>₹${values[i].toLocaleString("en-IN")}</td>
                        <td>${pct}%</td>
                    </tr>`;
                });

                html += `</tbody></table>`;
                chartDiv.innerHTML = html;
            }
        },
    });
}