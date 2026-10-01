# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

try:
    import frappe
    from frappe import _
except ImportError:
    frappe = None
    def _(msg):
        return msg

if not frappe:
    def whitelist(allow_guest=False, xss_safe=False):
        def decorator(fn):
            return fn
        return decorator

    class DummyFrappe:
        session = type('Session', (), {'user': 'Administrator'})()
        whitelist = staticmethod(whitelist)
    frappe = DummyFrappe()

@frappe.whitelist()
def get_dashboard_summary():
    """Returns total counts for active status categories."""
    if hasattr(frappe, "session") and getattr(frappe.session, "user", None) == "Guest":
        frappe.throw(_("Authentication required to view Valet Dashboard."), frappe.PermissionError)

    statuses = ["Awaiting Parking", "Parked", "Retrieval Requested", "On The Way"]
    summary = {status: 0 for status in statuses}

    if hasattr(frappe, "db") and frappe.db:
        counts = frappe.db.sql("""
            SELECT status, COUNT(*) as count 
            FROM `tabParking Ticket` 
            WHERE status IN ('Awaiting Parking', 'Parked', 'Retrieval Requested', 'On The Way')
            GROUP BY status
        """, as_dict=True)
        for row in counts:
            if row.status in summary:
                summary[row.status] = row.count
    return summary

@frappe.whitelist()
def get_active_tickets(search_query=None):
    """Fetches list of active parking tickets (excluding Delivered)."""
    if hasattr(frappe, "session") and getattr(frappe.session, "user", None) == "Guest":
        frappe.throw(_("Authentication required to view active tickets."), frappe.PermissionError)

    if not hasattr(frappe, "db") or not frappe.db:
        return []

    if search_query and str(search_query).strip():
        q = f"%{str(search_query).strip()}%"
        tickets = frappe.db.sql("""
            SELECT name, token_number, customer_whatsapp_number, vehicle_number, vehicle_type, status,
                   created_at, parked_at, retrieval_requested_at, on_the_way_at, delivered_at, modified
            FROM `tabParking Ticket`
            WHERE (token_number LIKE %s OR vehicle_number LIKE %s)
            ORDER BY modified DESC
        """, (q, q), as_dict=True)
    else:
        tickets = frappe.get_all(
            "Parking Ticket",
            fields=["name", "token_number", "customer_whatsapp_number", "vehicle_number", "vehicle_type", "status",
                    "created_at", "parked_at", "retrieval_requested_at", "on_the_way_at", "delivered_at", "modified"],
            filters=[["status", "!=", "Delivered"]],
            order_by="modified desc"
        )

    return tickets

@frappe.whitelist()
def update_ticket_status(token_number, next_status):
    """Updates ticket status using Document.save() to enforce server-side validation."""
    if hasattr(frappe, "session") and getattr(frappe.session, "user", None) == "Guest":
        frappe.throw(_("Authentication required to update ticket status."), frappe.PermissionError)

    if not token_number or not next_status:
        msg = _("Token Number and Next Status are required.")
        if hasattr(frappe, "throw"):
            frappe.throw(msg)
        else:
            raise ValueError(msg)

    # Re-use existing server-side Parking Ticket transition validation by loading doc & calling doc.save()
    if hasattr(frappe, "get_doc"):
        doc = frappe.get_doc("Parking Ticket", token_number)
        doc.status = next_status
        doc.save()
        return {
            "success": True,
            "message": _(f"Ticket {token_number} updated to '{next_status}' successfully."),
            "doc": doc.as_dict()
        }
    else:
        return {"success": False, "message": "Frappe framework unavailable"}
