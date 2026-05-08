import frappe

def get_context(context):
    context.no_cache = 1

    
    genre    = frappe.form_dict.get("genre", "")
    language = frappe.form_dict.get("language", "")

    filters = {"movie_status": "Now Showing"}
    if genre:    filters["genre"]    = genre
    if language: filters["language"] = language

    context.movies = frappe.get_all(
        "Movie",
        filters=filters,
        fields=[
            "name", "title", "poster",
            "language", "genre", "rating",
            "duration_minutes", "movie_status"
        ],
        order_by="creation desc"
    )

    context.genres = frappe.get_all(
        "Movie",
        filters={"movie_status": "Now Showing"},
        fields=["genre"], distinct=True
    )
    context.languages = frappe.get_all(
        "Movie",
        filters={"movie_status": "Now Showing"},
        fields=["language"], distinct=True
    )

    context.selected_genre    = genre
    context.selected_language = language
    context.title = "Now Showing"