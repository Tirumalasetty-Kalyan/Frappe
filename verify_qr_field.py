import frappe
frappe.init(site="valet.local")
frappe.connect()
doc = frappe.get_meta("Parking Ticket")
qr_field = doc.get_field("qr_code")
if qr_field:
    print(f"FOUND: fieldname={qr_field.fieldname}, fieldtype={qr_field.fieldtype}, label={qr_field.label}, read_only={qr_field.read_only}")
else:
    print("NOT FOUND: qr_code field missing from DocType meta")
frappe.destroy()
