import frappe

frappe.init(site="valet.local")
frappe.connect()

print("=" * 60)
print(" INSPECTING WEBHOOK LOGS FOR VEHICLE TS09AB1267")
print("=" * 60)

# 1. Search for Parking Ticket in database
tickets = frappe.get_all("Parking Ticket", filters={"vehicle_number": ["like", "%TS09AB1267%"]}, fields=["name", "token_number", "status", "customer_whatsapp_number", "created_at"])
print("\n1. PARKING TICKET SEARCH (TS09AB1267):")
if tickets:
    for t in tickets:
        print("   Found Ticket:", t)
else:
    print("   No Parking Ticket found for TS09AB1267")

# 2. Search Error Log table
error_logs = frappe.get_all("Error Log", filters={"method": ["like", "%whatsapp%"]}, fields=["name", "method", "error", "creation"], order_by="creation desc", limit=10)
if not error_logs:
    error_logs = frappe.get_all("Error Log", fields=["name", "method", "error", "creation"], order_by="creation desc", limit=10)

print("\n2. ERROR LOG TABLE SEARCH (Recent Errors):")
if error_logs:
    for err in error_logs:
        print(f"   Log ID: {err.name} | Method: {err.method} | Time: {err.creation}")
        print(f"   Error Snippet: {str(err.error)[:200]}")
else:
    print("   No error logs found in tabError Log.")

print("=" * 60)
