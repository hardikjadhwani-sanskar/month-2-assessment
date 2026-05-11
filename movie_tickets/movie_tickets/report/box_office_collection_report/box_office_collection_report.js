// box_office_collection_report.js

frappe.query_reports["Box Office Collection Report"] = {

    filters: [
        {
            fieldname: "theater",
            label:     __("Theater"),
            fieldtype: "Link",
            options:   "Theatre",
            width:     "100px"
        },
        {
            fieldname: "from_date",
            label:     __("From Date"),
            fieldtype: "Date",
            default:   frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            width:     "100px"
        },
        {
            fieldname: "to_date",
            label:     __("To Date"),
            fieldtype: "Date",
            default:   frappe.datetime.get_today(),
            width:     "100px"
        },
        {
            fieldname: "genre",
            label:     __("Genre"),
            fieldtype: "Link",
            options:   "Movie Genre",
            width:     "100px"
        },
        {
            fieldname: "language",
            label:     __("Language"),
            fieldtype: "Select",
            options:   "\nEnglish\nHindi\nGujarati\nTamil\nTelugu\nOther",
            width:     "100px"
        }
    ],

    // Highlight rows where occupancy > 80% in orange, 100% in red
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);

        if (column.fieldname === "avg_occupancy_pct" && data) {
            if (data.avg_occupancy_pct >= 100) {
                value = `<span style="color:#dc3545;font-weight:700;">${data.avg_occupancy_pct}%</span>`;
            } else if (data.avg_occupancy_pct >= 80) {
                value = `<span style="color:#fd7e14;font-weight:600;">${data.avg_occupancy_pct}%</span>`;
            } else {
                value = `<span style="color:#28a745;">${data.avg_occupancy_pct}%</span>`;
            }
        }

        if (column.fieldname === "total_revenue" && data) {
            value = `<strong>${value}</strong>`;
        }

        return value;
    },

    // Default chart shown when report loads
    get_dataviz_settings() {
        return {
            type:       "bar",
            fieldname:  "total_revenue",
            based_on:   "movie_title"
        };
    }
};