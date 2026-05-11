
import frappe
from frappe.client import get_count as original_get_count


def logged_get_count(doctype, filters=None, debug=False, cache=False):
    """
    Wrapper around frappe.client.get_count that logs every call.
    Registered via override_whitelisted_methods in hooks.py.
    """
    frappe.logger().info(
        f"[get_count] doctype={doctype} | filters={filters} | user={frappe.session.user}"
    )

    # Delegate to the original function — no behaviour change
    return original_get_count(
        doctype=doctype,
        filters=filters,
        debug=debug,
        cache=cache
    )
