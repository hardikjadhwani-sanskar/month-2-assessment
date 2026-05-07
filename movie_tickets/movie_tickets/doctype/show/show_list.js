frappe.listview_settings["Show"] = {

    get_indicator(doc) {

        if (doc.show_status === "Scheduled") {
            return [
                "Scheduled",
                "green",
                "show_status,=,Scheduled"
            ];
        }

        if (doc.show_status === "Now Playing") {
            return [
                "Now Playing",
                "orange",
                "show_status,=,Now Playing"
            ];
        }

        if (doc.show_status === "Completed") {
            return [
                "Completed",
                "gray",
                "show_status,=,Completed"
            ];
        }

        if (doc.show_status === "Cancelled") {
            return [
                "Cancelled",
                "red",
                "show_status,=,Cancelled"
            ];
        }

    }

};
