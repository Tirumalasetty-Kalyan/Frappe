import frappe

frappe.init(site="valet.local")
frappe.connect()

phone_id = frappe.conf.get("whatsapp_phone_number_id")
has_token = bool(frappe.conf.get("whatsapp_access_token"))

print("CONF CHECK:")
print("whatsapp_phone_number_id:", phone_id)
print("whatsapp_access_token configured:", has_token)
