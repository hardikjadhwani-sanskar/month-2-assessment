
import re
import frappe


def execute():
    """
    Patch: Generate slug from title for all Movies
    where slug is NULL or empty.

    Why this is needed:
        Movies created before the slug auto-generation logic
        was added to the before_save hook will have no slug.
        This patch backfills them all in one shot.
    """

    movies = frappe.db.sql("""
        SELECT name, title
        FROM `tabMovie`
        WHERE
            (slug IS NULL OR slug = '')
            AND (title IS NOT NULL AND title != '')
            
    """, as_dict=True)

    if not movies:
        frappe.logger().info("[Patch] set_movie_slugs: No movies need slug generation.")
        return

    updated = 0
    skipped = 0

    for movie in movies:
        slug = _generate_slug(movie.title)

        if not slug:
            frappe.logger().warning(
                f"[Patch] set_movie_slugs: Could not generate slug for '{movie.title}' ({movie.name}), skipping."
            )
            skipped += 1
            continue

        
        existing = frappe.db.get_value("Movie", {"slug": slug, "name": ["!=", movie.name]}, "name") 
        if existing:
            frappe.logger().warning(
                f"[Patch] set_movie_slugs: Slug '{slug}' for '{movie.title}' ({movie.name}) "
                f"already exists on Movie {existing}, skipping to avoid conflict."
            )
            skipped+=1
            continue

        frappe.db.set_value(
            "Movie",
            movie.name,
            "slug",
            slug,
            update_modified=False
        )

        frappe.logger().info(
            f"[Patch] set_movie_slugs: {movie.name} → slug='{slug}'"
        )
        updated += 1

    frappe.db.commit()
    frappe.logger().info(
        f"[Patch] set_movie_slugs: {updated} movie(s) updated, {skipped} skipped."
    )


def _generate_slug(title):
    """
    Mirrors the slug logic in Movie.before_save so patches
    produce identical slugs to what the live system generates.

    """
    if not title:
        return ""

    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug