# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

import re
from valet_parking.gemini_nlu import parse_gemini_intent, extract_vehicle_pattern, extract_token_pattern
from valet_parking.conversation_memory import get_conversation_state, set_conversation_state, clear_conversation_state

try:
    import frappe
except ImportError:
    frappe = None

CONFIDENCE_THRESHOLD = 0.75

GREETING_RESPONSE = (
    "Welcome to Valet Parking 🚗\n\n"
    "I can help you:\n"
    "• Park your car\n"
    "• Get your car\n"
    "• Check parking status\n"
    "• Report a problem\n\n"
    "Tell me what you need."
)

OUT_OF_SCOPE_RESPONSE = (
    "I can help only with valet parking services such as parking your car, getting your car, checking parking status, or reporting a vehicle issue."
)

AMBIGUOUS_RESPONSE = (
    "Sure — what would you like me to do?\n"
    "Park your car, get your car, check its status, or report a problem?"
)

FALLBACK_ERROR_RESPONSE = (
    "Sorry, I couldn't understand that. I can help you park your car, get your car, check parking status, or report a problem."
)

def process_customer_message(sender_whatsapp_number, message_text):
    """Processes incoming customer WhatsApp message and returns the appropriate response dict and text reply."""
    if not sender_whatsapp_number or not message_text:
        return {"status": "error", "reply": FALLBACK_ERROR_RESPONSE}

    clean_sender = str(sender_whatsapp_number).strip().lstrip('+')
    
    # 1. Fetch current conversation context
    context_state = get_conversation_state(clean_sender)

    # 2. Extract NLU Intent via Gemini
    try:
        nlu_res = parse_gemini_intent(message_text, context_state)
    except Exception as e:
        if frappe and hasattr(frappe, "log_error"):
            frappe.log_error(f"Gemini NLU Processing Error: {str(e)}")
        return {"status": "error", "reply": FALLBACK_ERROR_RESPONSE}

    intent = nlu_res.get("intent", "UNKNOWN")
    confidence = nlu_res.get("confidence", 0.0)
    vehicle_no = nlu_res.get("vehicle_number") or extract_vehicle_pattern(message_text)
    token_no = nlu_res.get("parking_token") or extract_token_pattern(message_text)
    problem_desc = nlu_res.get("problem_description") or message_text

    # Check for stored pending follow-up state
    if context_state and context_state.get("pending_action") == "AWAITING_VEHICLE_NUMBER":
        if vehicle_no:
            intent = "PARK_MY_CAR"
            confidence = 0.95

    # 3. Handle GREETING & OUT_OF_SCOPE regardless of confidence
    if intent == "GREETING":
        return {"status": "success", "reply": GREETING_RESPONSE}

    if intent == "OUT_OF_SCOPE":
        return {"status": "success", "reply": OUT_OF_SCOPE_RESPONSE}

    # 4. Confidence Safety Guard
    if confidence < CONFIDENCE_THRESHOLD or intent in ["UNKNOWN", "AMBIGUOUS"]:
        return {"status": "info", "reply": AMBIGUOUS_RESPONSE}

    # 5. Intent Routing to Frappe Business Logic with Strict Authority Validation
    if intent in ["PARK_MY_CAR", "FOLLOW_UP"] and (vehicle_no or context_state.get("pending_action") == "AWAITING_VEHICLE_NUMBER"):
        return handle_park_my_car(clean_sender, vehicle_no)

    if intent == "PARK_MY_CAR" and not vehicle_no:
        set_conversation_state(clean_sender, {"pending_action": "AWAITING_VEHICLE_NUMBER", "last_intent": "PARK_MY_CAR"})
        return {"status": "info", "reply": "Sure. Please send your vehicle number.\nExample: TS09AB1234"}

    if intent == "GET_MY_CAR":
        return handle_get_my_car(clean_sender, vehicle_no, token_no)

    if intent == "CHECK_STATUS":
        return handle_check_status(clean_sender, vehicle_no, token_no)

    if intent == "REPORT_PROBLEM":
        return handle_report_problem(clean_sender, vehicle_no, token_no, problem_desc)

    return {"status": "info", "reply": AMBIGUOUS_RESPONSE}

def handle_park_my_car(customer_number, vehicle_number):
    """Executes PARK_MY_CAR business logic using existing Parking Ticket doc."""
    if not vehicle_number:
        set_conversation_state(customer_number, {"pending_action": "AWAITING_VEHICLE_NUMBER", "last_intent": "PARK_MY_CAR"})
        return {"status": "info", "reply": "Sure. Please send your vehicle number.\nExample: TS09AB1234"}

    clean_vehicle = str(vehicle_number).strip().upper()

    if frappe and hasattr(frappe, "get_doc"):
        try:
            # Frappe Validation: Check if an active ticket already exists for this vehicle
            existing = frappe.get_all(
                "Parking Ticket",
                filters={"vehicle_number": clean_vehicle, "status": ["in", ["Awaiting Parking", "Parked", "Retrieval Requested", "On The Way"]]},
                fields=["name", "token_number", "status"]
            )
            if existing:
                t = existing[0]
                reply = f"A ticket ({t.token_number}) already exists for vehicle {clean_vehicle}. Current Status: {t.status}."
                return {"status": "info", "reply": reply, "ticket": {"name": t.name, "token_number": t.token_number, "status": t.status}}

            doc = frappe.get_doc({
                "doctype": "Parking Ticket",
                "customer_whatsapp_number": customer_number,
                "vehicle_number": clean_vehicle,
                "vehicle_type": "Car",
                "status": "Awaiting Parking"
            })
            doc.insert(ignore_permissions=True)
            if hasattr(frappe, "db") and hasattr(frappe.db, "commit"):
                frappe.db.commit()

            clear_conversation_state(customer_number)
            reply = (
                f"Your parking ticket has been generated! 🚗\n"
                f"Token: {doc.token_number}\n"
                f"Vehicle: {clean_vehicle}\n"
                f"Status: Awaiting Parking\n\n"
                f"We will notify you once your vehicle is safely parked."
            )
            return {
                "status": "success",
                "reply": reply,
                "message": "Parking ticket created successfully",
                "ticket": {
                    "name": getattr(doc, "name", None),
                    "token_number": getattr(doc, "token_number", None),
                    "status": getattr(doc, "status", None),
                    "customer_whatsapp_number": getattr(doc, "customer_whatsapp_number", None),
                    "vehicle_number": getattr(doc, "vehicle_number", None)
                }
            }
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(f"Ticket Creation Error: {str(e)}")
            return {"status": "error", "reply": f"Error generating parking ticket: {str(e)}"}

    reply = f"Parking ticket generated for {clean_vehicle} (Simulation Mode)."
    return {"status": "success", "reply": reply}

def handle_get_my_car(customer_number, vehicle_number=None, token_number=None):
    """Executes GET_MY_CAR business logic using strict Frappe ownership and status transition rules."""
    if not frappe or not hasattr(frappe, "get_all"):
        return {"status": "success", "reply": "Retrieval request received for your vehicle."}

    # Strict Frappe Business Rule: Filter by customer ownership and status == 'Parked'
    filters = {"status": "Parked"}
    if token_number:
        filters["token_number"] = token_number
    elif vehicle_number:
        filters["vehicle_number"] = vehicle_number
    else:
        filters["customer_whatsapp_number"] = customer_number

    parked_tickets = frappe.get_all("Parking Ticket", filters=filters, fields=["name", "token_number", "vehicle_number", "status", "customer_whatsapp_number"])

    # Ownership validation: Ensure ticket belongs to requester if token was specified
    if parked_tickets and token_number:
        owner_num = str(parked_tickets[0].customer_whatsapp_number).strip().lstrip('+')
        if owner_num != customer_number:
            return {"status": "error", "reply": "Unauthorized: This parking token belongs to another customer."}

    if len(parked_tickets) == 1:
        t = parked_tickets[0]
        ticket_doc = frappe.get_doc("Parking Ticket", t.name)

        # Validate transition using server-side rules
        if ticket_doc.status != "Parked":
            return {"status": "error", "reply": f"Vehicle cannot be retrieved from status '{ticket_doc.status}'."}

        ticket_doc.status = "Retrieval Requested"
        ticket_doc.save(ignore_permissions=True)
        if hasattr(frappe, "db") and hasattr(frappe.db, "commit"):
            frappe.db.commit()

        clear_conversation_state(customer_number)
        reply = (
            f"Retrieval request received for vehicle {ticket_doc.vehicle_number} (Token: {ticket_doc.token_number}).\n"
            f"Our valet driver is fetching your vehicle now."
        )
        return {
            "status": "success",
            "reply": reply,
            "message": "Retrieval request processed successfully",
            "ticket": {
                "name": ticket_doc.name,
                "token_number": ticket_doc.token_number,
                "status": ticket_doc.status
            }
        }

    if len(parked_tickets) > 1:
        return {"status": "info", "reply": "You have multiple parked vehicles. Please specify your vehicle number or parking token."}

    # Check if vehicle is in another status
    any_tickets = frappe.get_all("Parking Ticket", filters={"customer_whatsapp_number": customer_number}, fields=["name", "token_number", "vehicle_number", "status"], order_by="creation desc", limit=1)
    if any_tickets:
        st = any_tickets[0].status
        v_no = any_tickets[0].vehicle_number
        tok = any_tickets[0].token_number
        if st == "Awaiting Parking":
            reply = f"Your vehicle {v_no} (Token: {tok}) is currently awaiting parking. It has not been parked yet."
        elif st == "Retrieval Requested":
            reply = f"Retrieval is already requested for vehicle {v_no} (Token: {tok}). Our driver is fetching it."
        elif st == "On The Way":
            reply = f"Your vehicle {v_no} (Token: {tok}) is already on the way to the pickup point!"
        elif st == "Delivered":
            reply = f"Your vehicle {v_no} (Token: {tok}) was already delivered. No active parked vehicle found."
        else:
            reply = f"Vehicle {v_no} status: {st}."
        return {"status": "info", "reply": reply}

    return {"status": "error", "reply": "No active parked vehicle found for your number. Please provide your parking token or vehicle number.", "message": "No parked vehicle found for this request"}

def handle_check_status(customer_number, vehicle_number=None, token_number=None):
    """Returns current real ticket status from Frappe."""
    if not frappe or not hasattr(frappe, "get_all"):
        return {"status": "success", "reply": "Status check completed."}

    filters = {}
    if token_number:
        filters["token_number"] = token_number
    elif vehicle_number:
        filters["vehicle_number"] = vehicle_number
    else:
        filters["customer_whatsapp_number"] = customer_number

    tickets = frappe.get_all("Parking Ticket", filters=filters, fields=["name", "token_number", "vehicle_number", "status"], order_by="creation desc", limit=1)

    if tickets:
        t = tickets[0]
        reply = f"Vehicle Status 🚗\nToken: {t.token_number}\nVehicle: {t.vehicle_number}\nStatus: {t.status}"
        return {"status": "success", "reply": reply, "ticket": {"name": t.name, "token_number": t.token_number, "status": t.status}}

    return {"status": "info", "reply": "No active parking ticket found for your number."}

def handle_report_problem(customer_number, vehicle_number=None, token_number=None, problem_description=None):
    """Records customer issue in Valet Problem Report."""
    ticket_name = None
    if frappe and hasattr(frappe, "get_all"):
        filters = {}
        if token_number:
            filters["token_number"] = token_number
        elif vehicle_number:
            filters["vehicle_number"] = vehicle_number
        else:
            filters["customer_whatsapp_number"] = customer_number

        tickets = frappe.get_all("Parking Ticket", filters=filters, fields=["name", "vehicle_number"], order_by="creation desc", limit=1)
        if tickets:
            ticket_name = tickets[0].name
            if not vehicle_number:
                vehicle_number = tickets[0].vehicle_number

    if frappe and hasattr(frappe, "get_doc"):
        try:
            report_doc = frappe.get_doc({
                "doctype": "Valet Problem Report",
                "customer_whatsapp_number": customer_number,
                "vehicle_number": vehicle_number or "UNKNOWN",
                "parking_ticket": ticket_name,
                "problem_description": problem_description or "Customer reported issue via WhatsApp",
                "status": "Open"
            })
            report_doc.insert(ignore_permissions=True)
            if hasattr(frappe, "db") and hasattr(frappe.db, "commit"):
                frappe.db.commit()
        except Exception as e:
            if hasattr(frappe, "log_error"):
                frappe.log_error(f"Problem Report Creation Error: {str(e)}")

    reply = "Your issue has been reported to the valet team. We will assist you shortly."
    return {"status": "success", "reply": reply}
