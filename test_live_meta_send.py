import frappe
from valet_parking.valet_parking.api import send_whatsapp_message, send_whatsapp_notification

frappe.init(site="valet.local")
frappe.connect()

print("=" * 60)
print(" LIVE META WHATSAPP DISPATCH TEST WITH FRESH TOKEN")
print("=" * 60)

recipient_number = "+918331820779"
phone_id = frappe.conf.get("whatsapp_phone_number_id")
has_token = bool(frappe.conf.get("whatsapp_access_token"))

print("Phone Number ID:", phone_id)
print("Access Token Configured:", has_token)
print("Target Recipient Number:", recipient_number)

# 1. Direct message test via send_whatsapp_message()
test_message = "Valet Parking Notification: Your vehicle TS09EA1234 has been safely parked! Token: VP-TEST01. Reply 'Get My Car' when ready."
res1 = send_whatsapp_message(recipient_number, test_message)

print("\n--- DISPATCH RESULT ---")
print("Status:", res1.get("status"))
print("Meta API Response:", res1.get("api_response"))
if res1.get("message"):
    print("Error Message:", res1.get("message"))

print("=" * 60)
