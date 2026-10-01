import json
import frappe
from unittest.mock import MagicMock
from valet_parking.valet_parking.api import handle_whatsapp_webhook, send_whatsapp_message

frappe.init(site="valet.local")
frappe.connect()

print("=" * 70)
print(" LIVE E2E VALET PARKING LIFECYCLE TEST (META CLOUD API)")
print("=" * 70)

customer_number = "+918331820779"
vehicle_number = "TS09EA8888"

results = {
    "token_number": None,
    "transitions": [],
    "whatsapp_messages": [],
    "timestamps": {},
    "final_status": None
}

# -------------------------------------------------------------
# 1 & 2: Simulate Incoming Webhook Message -> Ticket Creation
# -------------------------------------------------------------
print("\n--- Step 1 & 2: Incoming Webhook (Ticket Creation) ---")
meta_payload = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "LIVE_E2E_ACC",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "messages": [{
                    "from": customer_number,
                    "id": "wamid.live.1",
                    "timestamp": "1670000099",
                    "text": {"body": f"Please park my car {vehicle_number}"},
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}
raw_data = json.dumps(meta_payload).encode('utf-8')
frappe.request = MagicMock()
frappe.request.method = "POST"
frappe.request.get_data.return_value = raw_data
frappe.request.headers = {"X-Webhook-Token": "valet_parking_token"}
frappe.request.args = {}

res_create = handle_whatsapp_webhook()
print("Webhook Response:", res_create)

ticket_info = res_create.get("ticket", {})
ticket_name = ticket_info.get("name")
token_number = ticket_info.get("token_number")
results["token_number"] = token_number
results["transitions"].append(("Created", ticket_info.get("status")))

ticket = frappe.get_doc("Parking Ticket", ticket_name)
results["timestamps"]["created_at"] = str(ticket.created_at)

print(f"Created Ticket: {ticket.name} | Token: {token_number} | Status: {ticket.status} | CreatedAt: {ticket.created_at}")
assert ticket.status == "Awaiting Parking"
assert ticket.customer_whatsapp_number == customer_number
assert ticket.vehicle_number == vehicle_number

# -------------------------------------------------------------
# 3 & 4: Transition to 'Parked' & Dispatch Notification
# -------------------------------------------------------------
print("\n--- Step 3 & 4: Transition to 'Parked' & WhatsApp Notification ---")
ticket.status = "Parked"
ticket.save(ignore_permissions=True)
frappe.db.commit()

ticket.reload()
results["transitions"].append(("Awaiting Parking -> Parked", ticket.status))
results["timestamps"]["parked_at"] = str(ticket.parked_at)

msg1_text = f"Your vehicle {vehicle_number} has been safely parked! Token: {token_number}. Reply 'Get My Car' when ready to retrieve."
res_meta1 = send_whatsapp_message(customer_number, msg1_text)
print("Parked Meta Dispatch Result:", res_meta1)
meta_response1 = res_meta1.get("api_response", {})
is_accepted1 = "messages" in meta_response1
wamid1 = meta_response1.get("messages", [{}])[0].get("id") if is_accepted1 else None
results["whatsapp_messages"].append({"stage": "Parked", "accepted": is_accepted1, "wamid": wamid1, "error": meta_response1.get("error")})

# -------------------------------------------------------------
# 5, 6 & 7: Incoming "Get My Car" Webhook -> 'Retrieval Requested'
# -------------------------------------------------------------
print("\n--- Step 5, 6 & 7: Incoming 'Get My Car' Webhook & Notification ---")
retrieval_payload = {
    "from": customer_number,
    "message": "Get My Car"
}
raw_data = json.dumps(retrieval_payload).encode('utf-8')
frappe.request = MagicMock()
frappe.request.method = "POST"
frappe.request.get_data.return_value = raw_data
frappe.request.headers = {"X-Webhook-Token": "valet_parking_token"}

res_retrieval_wh = handle_whatsapp_webhook()
print("Get My Car Webhook Response:", res_retrieval_wh)

ticket.reload()
results["transitions"].append(("Parked -> Retrieval Requested", ticket.status))
results["timestamps"]["retrieval_requested_at"] = str(ticket.retrieval_requested_at)

msg2_text = f"Retrieval request received for vehicle {vehicle_number} (Token: {token_number}). Our driver is fetching your car."
res_meta2 = send_whatsapp_message(customer_number, msg2_text)
print("Retrieval Requested Meta Dispatch Result:", res_meta2)
meta_response2 = res_meta2.get("api_response", {})
is_accepted2 = "messages" in meta_response2
wamid2 = meta_response2.get("messages", [{}])[0].get("id") if is_accepted2 else None
results["whatsapp_messages"].append({"stage": "Retrieval Requested", "accepted": is_accepted2, "wamid": wamid2, "error": meta_response2.get("error")})

# -------------------------------------------------------------
# 8 & 9: Transition to 'On The Way' & Dispatch Notification
# -------------------------------------------------------------
print("\n--- Step 8 & 9: Transition to 'On The Way' & Notification ---")
ticket.status = "On The Way"
ticket.save(ignore_permissions=True)
frappe.db.commit()

ticket.reload()
results["transitions"].append(("Retrieval Requested -> On The Way", ticket.status))
results["timestamps"]["on_the_way_at"] = str(ticket.on_the_way_at)

msg3_text = f"Your vehicle {vehicle_number} (Token: {token_number}) is on the way to the pickup point!"
res_meta3 = send_whatsapp_message(customer_number, msg3_text)
print("On The Way Meta Dispatch Result:", res_meta3)
meta_response3 = res_meta3.get("api_response", {})
is_accepted3 = "messages" in meta_response3
wamid3 = meta_response3.get("messages", [{}])[0].get("id") if is_accepted3 else None
results["whatsapp_messages"].append({"stage": "On The Way", "accepted": is_accepted3, "wamid": wamid3, "error": meta_response3.get("error")})

# -------------------------------------------------------------
# 10, 11, 12 & 13: Transition to 'Delivered' & Dispatch Notification
# -------------------------------------------------------------
print("\n--- Step 10, 11, 12 & 13: Transition to 'Delivered' & Verification ---")
ticket.status = "Delivered"
ticket.save(ignore_permissions=True)
frappe.db.commit()

ticket.reload()
results["transitions"].append(("On The Way -> Delivered", ticket.status))
results["timestamps"]["delivered_at"] = str(ticket.delivered_at)
results["final_status"] = ticket.status

msg4_text = f"Your vehicle {vehicle_number} (Token: {token_number}) has been delivered. Thank you for using Valet Parking!"
res_meta4 = send_whatsapp_message(customer_number, msg4_text)
print("Delivered Meta Dispatch Result:", res_meta4)
meta_response4 = res_meta4.get("api_response", {})
is_accepted4 = "messages" in meta_response4
wamid4 = meta_response4.get("messages", [{}])[0].get("id") if is_accepted4 else None
results["whatsapp_messages"].append({"stage": "Delivered", "accepted": is_accepted4, "wamid": wamid4, "error": meta_response4.get("error")})

print("\n" + "=" * 70)
print(" SUMMARY OF LIVE E2E LIFECYCLE EXECUTION")
print("=" * 70)
print("Ticket Token:", results["token_number"])
print("Final Status:", results["final_status"])
print("Timestamps Recorded:", results["timestamps"])
print("Status Transitions:", results["transitions"])
print("Meta WhatsApp Deliveries:", results["whatsapp_messages"])
print("=" * 70)
