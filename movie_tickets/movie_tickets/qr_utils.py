# movie_tickets/qr_utils.py

import io
import os
import base64
import qrcode
import frappe
from frappe.utils import get_site_path


def generate_booking_qr(booking_name):
    """
    Generates a QR code image for a booking, saves it as a File
    attachment on the Ticket Booking record, and returns the file URL.
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

    img = qr.make_image(fill_color="black", back_color="white")

    # Save to a BytesIO buffer
    buffer = io.BytesIO()
    img = img.convert("RGB")
    img.save(buffer, format="PNG")
    buffer.seek(0)

    # Save as a Frappe File attached to the booking
    filename = f"qr_{booking_name.replace('/', '-')}.png"

    # Remove old QR file if it exists
    old_file = frappe.db.get_value(
        "File",
        {"attached_to_doctype": "Ticket Booking",
         "attached_to_name": booking_name,
         "file_name": filename},
        "name"
    )
    if old_file:
        frappe.delete_doc("File", old_file, ignore_permissions=True)

    # Save new file
    file_doc = frappe.get_doc({
        "doctype":            "File",
        "file_name":          filename,
        "attached_to_doctype": "Ticket Booking",
        "attached_to_name":   booking_name,
        "content":            buffer.read(),
        "is_private":         0
    })
    file_doc.save(ignore_permissions=True)

    # Store the URL on the booking record
    frappe.db.set_value(
        "Ticket Booking", booking_name,
        "qr_code_url", file_doc.file_url,
        update_modified=False
    )

    return file_doc.file_url