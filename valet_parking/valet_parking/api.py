# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

import json
import re
import hmac
import hashlib
from urllib.parse import parse_qs

try:
    import frappe
except ImportError:
    frappe = None

def get_webhook_secret():
    """Returns configured webhook secret/token or default token for verification."""
    if frappe and hasattr(frappe, "conf") and frappe.conf:
        return getattr(frappe.conf, "whatsapp_webhook_secret", None) or getattr(frappe.conf, "whatsapp_verify_token", None) or "valet_parking_token"
    return "valet_parking_token"

def validate_webhook_signature(request_data, headers):
    """Validates incoming webhook signature/token for security."""
    secret = get_webhook_secret()
    
    # 1. Header token verification (X-Webhook-Token, X-WhatsApp-Token, or X-Verify-Token)
    token_header = headers.get("X-Webhook-Token") or headers.get("X-WhatsApp-Token") or headers.get("X-Verify-Token") or headers.get("x-webhook-token") or headers.get("x-whatsapp-token")
    if token_header and token_header == secret:
        return True
        
    # 2. Query param token verification (?secret=... or ?token=...)
    if frappe and hasattr(frappe, "request") and frappe.request and getattr(frappe.request, "args", None):
        req_token = frappe.request.args.get("secret") or frappe.request.args.get("token") or frappe.request.args.get("verify_token")
        if req_token and req_token == secret:
            return True

    # 3. Meta X-Hub-Signature-256 validation (HMAC SHA-256)
    meta_sig = headers.get("X-Hub-Signature-256") or headers.get("x-hub-signature-256")
    if meta_sig and secret:
        raw_bytes = request_data if isinstance(request_data, bytes) else str(request_data).encode('utf-8')
        expected_sig = "sha256=" + hmac.new(secret.encode('utf-8'), raw_bytes, hashlib.sha256).hexdigest()
        if hmac.compare_digest(meta_sig, expected_sig):
            return True

    # Allow default test/local requests if default token is configured and no specific signature is provided
    if secret == "valet_parking_token" and not meta_sig and not token_header:
        return True

    return False

def extract_vehicle_number(text):
    """Extracts vehicle registration number pattern from message text."""
    if not text:
        return None
    pattern = r'\b([A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4})\b'
    match = re.search(pattern, str(text).strip().upper())
    if match:
        return match.group(1)
    
    cleaned = re.sub(r'[^A-Z0-9]', '', str(text).strip().upper())
    if 4 <= len(cleaned) <= 12:
        return cleaned
    return None

def is_retrieval_request(text):
    """Checks if message text indicates a vehicle retrieval request ('Get My Car', token, etc.)."""
    if not text:
        return False
    t = str(text).strip().upper()
    keywords = ["GET MY CAR", "GET CAR", "RETRIEVE", "REQUEST CAR", "FETCH CAR", "NEED MY CAR", "BRING CAR"]
    if any(k in t for k in keywords):
        return True
    if re.search(r'\bVP-[A-Z0-9]{6}\b', t):
        return True
    return False

def send_whatsapp_message(to_number, text):
    """Dispatches outgoing WhatsApp message via Meta Cloud API or simulation mode."""
    if not to_number or not text:
        return {"status": "error", "message": "Missing recipient or text"}

    cleaned_number = re.sub(r'[^0-9+]', '', str(to_number).strip())
    
    # Check if Meta API credentials are configured in frappe.conf
    api_token = getattr(frappe.conf, "whatsapp_access_token", None) if frappe and hasattr(frappe, "conf") and frappe.conf else None
    phone_number_id = getattr(frappe.conf, "whatsapp_phone_number_id", None) if frappe and hasattr(frappe, "conf") and frappe.conf else None
    
    if api_token and phone_number_id:
        url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": cleaned_number.lstrip('+'),
            "type": "text",
            "text": {"body": text}
        }
        try:
            import requests
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            return {"status": "sent", "api_response": response.json()}
        except Exception as e:
            if frappe and hasattr(frappe, "log_error"):
                frappe.log_error(f"WhatsApp API Dispatch Error: {str(e)}")
            return {"status": "error", "message": str(e)}

    # Simulation / Test mode recording
    log_entry = {
        "status": "simulated",
        "to": cleaned_number,
        "text": text
    }
    if frappe and hasattr(frappe, "flags"):
        if not hasattr(frappe.flags, "sent_whatsapp_messages"):
            frappe.flags.sent_whatsapp_messages = []
        frappe.flags.sent_whatsapp_messages.append(log_entry)
    
    return log_entry

def send_whatsapp_notification(ticket, status):
    """Formats and dispatches customer notification for ticket status updates."""
    if not ticket or not status:
        return

    to_number = getattr(ticket, "customer_whatsapp_number", None)
    token = getattr(ticket, "token_number", "")
    vehicle_no = getattr(ticket, "vehicle_number", "")

    if not to_number:
        return

    text = None
    if status == "Parked":
        text = (
            f"Your vehicle {vehicle_no} has been safely parked!\n"
            f"Token: {token}\n"
            f"To request your vehicle when ready, reply 'Get My Car' or send your token number."
        )
    elif status == "Retrieval Requested":
        text = (
            f"Retrieval request received for vehicle {vehicle_no} (Token: {token}).\n"
            f"Our valet driver is fetching your vehicle now."
        )
    elif status == "On The Way":
        text = (
            f"Your vehicle {vehicle_no} (Token: {token}) is on the way to the pickup point!"
        )
    elif status == "Delivered":
        text = (
            f"Your vehicle {vehicle_no} (Token: {token}) has been delivered.\n"
            f"Thank you for using our Valet Parking service!"
        )

    if text:
        send_whatsapp_message(to_number, text)

if frappe and hasattr(frappe, "whitelist"):
    whitelist_dec = frappe.whitelist
else:
    def whitelist_dec(*args, **kwargs):
        def decorator(fn):
            return fn
        return decorator

@whitelist_dec(allow_guest=True)
def handle_whatsapp_webhook(*args, **kwargs):
    """Frappe Whitelisted endpoint for incoming WhatsApp webhook (GET verification & POST events)."""
    if not frappe:
        return {"status": "error", "message": "Frappe framework not available"}

    request = getattr(frappe, "request", None)
    
    # -------------------------------------------------------------
    # 1. Handle GET Webhook Verification (e.g. Meta Cloud API setup)
    # -------------------------------------------------------------
    if request and getattr(request, "method", "GET") == "GET":
        args_dict = getattr(request, "args", {}) or {}
        mode = args_dict.get("hub.mode") or args_dict.get("mode")
        token = args_dict.get("hub.verify_token") or args_dict.get("verify_token")
        challenge = args_dict.get("hub.challenge") or args_dict.get("challenge")
        
        secret = get_webhook_secret()
        if mode == "subscribe" and token == secret:
            challenge_str = str(challenge) if challenge is not None else "OK"
            if hasattr(frappe, "response"):
                frappe.response["type"] = "download"
                frappe.response["content_type"] = "text/plain"
                frappe.response["display_content_as"] = "inline"
                frappe.response["filename"] = "challenge.txt"
                frappe.response["filecontent"] = challenge_str
                frappe.response["result"] = challenge_str
                frappe.response["http_status_code"] = 200
            return challenge_str
        if hasattr(frappe, "respond_as_web_page"):
            frappe.respond_as_web_page("Unauthorized", "Webhook verification failed", http_status_code=403)
        if hasattr(frappe, "response"):
            frappe.response["http_status_code"] = 403
        return {"status": "error", "message": "Webhook verification failed"}

    # -------------------------------------------------------------
    # 2. Handle POST Webhook Event Payload
    # -------------------------------------------------------------
    headers = dict(request.headers) if request and hasattr(request, "headers") and request.headers else {}
    raw_data = request.get_data() if request and hasattr(request, "get_data") else b""

    # Validate security signature / token
    if not validate_webhook_signature(raw_data, headers):
        if hasattr(frappe, "response"):
            frappe.response["http_status_code"] = 401
        return {"status": "error", "message": "Invalid or missing webhook signature/token"}

    # Parse payload body
    payload = {}
    if raw_data:
        try:
            payload = json.loads(raw_data.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            try:
                payload = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in parse_qs(raw_data.decode('utf-8')).items()}
            except Exception:
                payload = {}
    if not payload and kwargs:
        payload = kwargs

    sender_whatsapp_number = None
    message_text = None

    # Meta WhatsApp Cloud API format parsing
    if "entry" in payload and isinstance(payload["entry"], list) and payload["entry"]:
        for entry in payload["entry"]:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    sender_whatsapp_number = msg.get("from")
                    if msg.get("type") == "text":
                        message_text = msg.get("text", {}).get("body")
                    elif msg.get("type") == "interactive":
                        interactive = msg.get("interactive", {})
                        if interactive.get("type") == "button_reply":
                            reply = interactive.get("button_reply", {})
                            message_text = reply.get("title") or reply.get("id")
                    elif msg.get("body"):
                        message_text = msg.get("body")
                    if sender_whatsapp_number and message_text:
                        break

    # Twilio or Direct payload format parsing
    if not sender_whatsapp_number:
        sender_whatsapp_number = payload.get("from") or payload.get("From") or payload.get("whatsapp_number") or payload.get("customer_whatsapp_number")
        if sender_whatsapp_number and str(sender_whatsapp_number).startswith("whatsapp:"):
            sender_whatsapp_number = str(sender_whatsapp_number).replace("whatsapp:", "").strip()

    if not message_text:
        message_text = payload.get("body") or payload.get("Body") or payload.get("message") or payload.get("text")

    if not sender_whatsapp_number:
        return {"status": "ignored", "message": "No sender WhatsApp number found in payload"}

    clean_sender = str(sender_whatsapp_number).strip()

    # -------------------------------------------------------------
    # 3. Pass message through Gemini NLU + Bot Engine
    # -------------------------------------------------------------
    try:
        from valet_parking.bot_engine import process_customer_message
        res_dict = process_customer_message(clean_sender, message_text or payload.get("vehicle_number") or "")
        
        # Send outgoing WhatsApp reply if message text/reply exists
        reply_text = res_dict.get("reply")
        if reply_text:
            send_whatsapp_message(clean_sender, reply_text)
            
        return res_dict
    except Exception as e:
        if frappe and hasattr(frappe, "log_error"):
            frappe.log_error(f"WhatsApp Webhook Bot Engine Error: {str(e)}")
        return {
            "status": "error",
            "message": "Sorry, I couldn't understand that. I can help you park your car, get your car, check parking status, or report a problem."
        }

