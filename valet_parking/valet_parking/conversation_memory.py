# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

import json
import time

try:
    import frappe
except ImportError:
    frappe = None

_IN_MEMORY_CACHE = {}

def get_conversation_state(whatsapp_number):
    """Retrieves conversation context for a WhatsApp customer number."""
    if not whatsapp_number:
        return {}
    clean_num = str(whatsapp_number).strip().lstrip('+')
    
    if frappe and hasattr(frappe, "cache") and frappe.cache():
        try:
            val = frappe.cache().get_value(f"valet_parking:conv:{clean_num}")
            if val:
                return json.loads(val) if isinstance(val, str) else val
        except Exception:
            pass

    entry = _IN_MEMORY_CACHE.get(clean_num)
    if entry and (time.time() - entry.get("timestamp", 0)) < 1800:
        return entry.get("state", {})
    return {}

def set_conversation_state(whatsapp_number, state_dict, ttl=1800):
    """Saves conversation context state for a WhatsApp customer number."""
    if not whatsapp_number or not state_dict:
        return
    clean_num = str(whatsapp_number).strip().lstrip('+')
    
    if frappe and hasattr(frappe, "cache") and frappe.cache():
        try:
            frappe.cache().set_value(f"valet_parking:conv:{clean_num}", json.dumps(state_dict), expires_in_sec=ttl)
            return
        except Exception:
            pass

    _IN_MEMORY_CACHE[clean_num] = {
        "state": state_dict,
        "timestamp": time.time()
    }

def clear_conversation_state(whatsapp_number):
    """Clears conversation context state for a WhatsApp customer number."""
    if not whatsapp_number:
        return
    clean_num = str(whatsapp_number).strip().lstrip('+')
    
    if frappe and hasattr(frappe, "cache") and frappe.cache():
        try:
            frappe.cache().delete_value(f"valet_parking:conv:{clean_num}")
        except Exception:
            pass

    _IN_MEMORY_CACHE.pop(clean_num, None)
