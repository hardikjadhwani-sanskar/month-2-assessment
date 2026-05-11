# movie_tickets/qr_utils.py

import io
import os
import base64
import qrcode
import frappe
from frappe.utils import get_site_path


def generate_booking_qr(booking_name):
    """
    Generates a QR code PNG for a booking.
    Saves it to the public files directory directly (not via File doc content field)
    so the path is predictable and base64 encoding in email works reliably.
    Returns the file URL e.g. /files/qr_BKG-2026-00001.png
    """
    doc = frappe.get_doc("Ticket Booking", booking_name)

    seat_labels = ", ".join([s.seat_label for s in (doc.seats or [])])

    # QR content — structured text scanned at entry gate
    qr_content = (
        f"BOOKING:{doc.name}\n"
        f"MOVIE:{doc.movie_title}\n"
        f"THEATRE:{doc.theatre}\n"
        f"SCREEN:{doc.screen}\n"
        f"DATE:{doc.show_date}\n"
        f"TIME:{str(doc.start_time)[:5]}\n"
        f"SEATS:{seat_labels}\n"
        f"AMOUNT:{doc.total_amount}\n"
        f"STATUS:{doc.booking_status}"
    )

    # Generate QR image
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(qr_content)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # ── Save PNG bytes to buffer ──────────────────────────────────────────────
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()   # getvalue() works without seek — safer than read()

    # ── Write file directly to site's public/files directory ─────────────────
    # This makes the path 100% predictable for base64 reading later
    safe_name = booking_name.replace("/", "-").replace(" ", "_")
    filename  = f"qr_{safe_name}.png"

    # Absolute path: /home/user/bench/sites/your-site/public/files/qr_BKG-....png
    file_dir  = get_site_path("public", "files")
    file_path = os.path.join(file_dir, filename)

    os.makedirs(file_dir, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(image_bytes)

    # ── Register as Frappe File record so it appears in attachments ──────────
    file_url = f"/files/{filename}"

    # Remove old File record if exists (avoid duplicates in attachment list)
    old_file = frappe.db.get_value(
        "File",
        {
            "attached_to_doctype": "Ticket Booking",
            "attached_to_name":    booking_name,
            "file_name":           filename
        },
        "name"
    )
    if old_file:
        frappe.delete_doc("File", old_file, ignore_permissions=True)

    # Create new File record pointing to the already-saved file
    file_doc = frappe.get_doc({
        "doctype":             "File",
        "file_name":           filename,
        "file_url":            file_url,       # explicit URL — no content upload needed
        "attached_to_doctype": "Ticket Booking",
        "attached_to_name":    booking_name,
        "is_private":          0               # public so email can read it
    })
    file_doc.insert(ignore_permissions=True)

    # ── Store URL on booking record ───────────────────────────────────────────
    frappe.db.set_value(
        "Ticket Booking", booking_name,
        "qr_code_url", file_url,
        update_modified=False
    )

    frappe.logger().info(
        f"[QR] Generated for {booking_name} → {file_path}"
    )

    return file_url