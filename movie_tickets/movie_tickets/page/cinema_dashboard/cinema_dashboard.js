// cinema_dashboard.js

frappe.pages["cinema-dashboard"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent:    wrapper,
        title:     "Cinema Dashboard",
        single_column: true
    });

    // Load Chart.js from CDN
    frappe.require(
        "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js",
        () => { render_dashboard(page, wrapper); }
    );
};

function render_dashboard(page, wrapper) {
    $(wrapper).find(".page-content").html(`
        <div style="padding:20px;">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
                <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;">
                    <h3 style="margin:0 0 16px;font-size:14px;color:#555;">
                        Today's Occupancy by Theatre
                    </h3>
                    <canvas id="occupancy-chart" height="200"></canvas>
                </div>
                <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;">
                    <h3 style="margin:0 0 16px;font-size:14px;color:#555;">
                        Top 5 Movies by Bookings (30 days)
                    </h3>
                    <canvas id="movies-chart" height="200"></canvas>
                </div>
            </div>
            <div style="display:grid;grid-template-columns:2fr 1fr;gap:20px;">
                <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;">
                    <h3 style="margin:0 0 16px;font-size:14px;color:#555;">
                        30-Day Revenue Trend
                    </h3>
                    <canvas id="revenue-chart" height="120"></canvas>
                </div>
                <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:20px;">
                    <h3 style="margin:0 0 16px;font-size:14px;color:#555;">
                        Bookings by Time Slot
                    </h3>
                    <canvas id="timeslot-chart" height="200"></canvas>
                </div>
            </div>
        </div>
    `);

    frappe.call({
        method: "movie_tickets.movie_tickets.page.cinema_dashboard.cinema_dashboard.get_dashboard_data",
        callback(r) {
            if (r.exc || !r.message) return;
            const data = r.message;

            // 1. Occupancy Bar Chart
            new Chart(document.getElementById("occupancy-chart"), {
                type: "bar",
                data: {
                    labels:   data.occupancy_by_theatre.map(d => d.theatre),
                    datasets: [{
                        label:           "Occupancy %",
                        data:            data.occupancy_by_theatre.map(d => d.occupancy_pct),
                        backgroundColor: data.occupancy_by_theatre.map(d =>
                            d.occupancy_pct >= 90 ? "#dc3545" :
                            d.occupancy_pct >= 60 ? "#ffc107" : "#4CAF50"
                        )
                    }]
                },
                options: {
                    responsive: true,
                    scales: { y: { min: 0, max: 100,
                        ticks: { callback: v => v + "%" } } },
                    plugins: { legend: { display: false } }
                }
            });

            // 2. Top Movies Donut Chart
            new Chart(document.getElementById("movies-chart"), {
                type: "doughnut",
                data: {
                    labels:   data.top_movies.map(d => d.movie_title),
                    datasets: [{
                        data: data.top_movies.map(d => d.bookings),
                        backgroundColor: [
                            "#4CAF50","#2196F3","#FF9800","#9C27B0","#F44336"
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { position: "bottom" } }
                }
            });

            // 3. Revenue Trend Line Chart
            new Chart(document.getElementById("revenue-chart"), {
                type: "line",
                data: {
                    labels:   data.revenue_trend.map(d => d.date),
                    datasets: [{
                        label:       "Revenue (₹)",
                        data:        data.revenue_trend.map(d => d.revenue),
                        borderColor: "#2196F3",
                        backgroundColor: "rgba(33,150,243,0.1)",
                        tension:     0.4,
                        fill:        true
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { ticks: { callback: v => "₹" + v.toLocaleString() } }
                    }
                }
            });

            // 4. Time Slot Histogram (Bar)
            new Chart(document.getElementById("timeslot-chart"), {
                type: "bar",
                data: {
                    labels:   data.bookings_by_timeslot.map(d => d.time_slot),
                    datasets: [{
                        label:           "Bookings",
                        data:            data.bookings_by_timeslot.map(d => d.bookings),
                        backgroundColor: "#9C27B0"
                    }]
                },
                options: {
                    responsive: true,
                    indexAxis: "y",  // horizontal bar
                    plugins: { legend: { display: false } }
                }
            });
        }
    });
}