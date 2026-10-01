# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

import json
import re
import urllib.request
import urllib.error

try:
    import frappe
except ImportError:
    frappe = None

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"

GEMINI_SYSTEM_PROMPT = """You are a Natural Language Understanding (NLU) classifier for a Valet Parking WhatsApp assistant.
Analyze the incoming customer message and output ONLY a valid JSON object matching this exact schema:

{
  "intent": "GREETING" | "PARK_MY_CAR" | "GET_MY_CAR" | "CHECK_STATUS" | "REPORT_PROBLEM" | "FOLLOW_UP" | "OUT_OF_SCOPE" | "UNKNOWN",
  "vehicle_number": string | null,
  "parking_token": string | null,
  "problem_description": string | null,
  "confidence": float between 0.0 and 1.0
}

INTENT DEFINITIONS:
1. GREETING: Hello, hi, good morning, hey, help, what can you do.
2. PARK_MY_CAR: User wants to park a vehicle (e.g., "Park my car", "I am here to park", "Take my vehicle", "Please park TS09AB1234").
3. GET_MY_CAR: User wants to retrieve/fetch their parked car (e.g., "Bring my car", "I want my car", "Can you get my vehicle", "Fetch my car to entrance", "VP-ABC123").
4. CHECK_STATUS: User asks about current ticket status (e.g., "Where is my car", "Is my car parked yet", "Status of vehicle", "Has my car arrived").
5. REPORT_PROBLEM: User complains or reports an issue (e.g., "Car hasn't arrived", "Vehicle delayed", "Something wrong with my car", "I want to complain", "Damage report").
6. FOLLOW_UP: Message contains a standalone vehicle number (e.g. "TS09AB1234"), token ("VP-123456"), or brief reply answering a previous question.
7. OUT_OF_SCOPE: Unrelated requests (e.g., weather, jokes, news, metro timing, general knowledge).
8. UNKNOWN: Vague, ambiguous, or unclassifiable message (e.g., "my car", "bring it").

ENTITY EXTRACTION:
- vehicle_number: Standardized uppercase vehicle registration (e.g., "TS09AB1234", "KA01AB9999").
- parking_token: Standardized uppercase parking token (e.g., "VP-ABC123", "VP-123456").
- problem_description: Brief summary if REPORT_PROBLEM, else null.
- confidence: Float 0.0 to 1.0 representing classification confidence.

Do not output any markdown formatting, markdown code blocks (no ```json), explanations, or extra text. Output ONLY the raw JSON string."""

def extract_vehicle_pattern(text):
    """Regex extraction of vehicle registration numbers."""
    if not text:
        return None
    match = re.search(r'\b([A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4})\b', str(text).upper())
    if match:
        return match.group(1)
    cleaned = re.sub(r'[^A-Z0-9]', '', str(text).upper())
    if 4 <= len(cleaned) <= 12 and re.search(r'[A-Z]', cleaned) and re.search(r'[0-9]', cleaned):
        return cleaned
    return None

def extract_token_pattern(text):
    """Regex extraction of parking token numbers."""
    if not text:
        return None
    match = re.search(r'\b(VP-[A-Z0-9]{6})\b', str(text).upper())
    return match.group(1) if match else None

def parse_gemini_intent(message_text, context_state=None):
    """Calls Google Gemini API (via GenAI SDK or REST API) for intent classification."""
    fallback_res = {
        "intent": "UNKNOWN",
        "vehicle_number": extract_vehicle_pattern(message_text),
        "parking_token": extract_token_pattern(message_text),
        "problem_description": None,
        "confidence": 0.0
    }

    if not message_text:
        return fallback_res

    api_key = getattr(frappe.conf, "gemini_api_key", None) if frappe and hasattr(frappe, "conf") and frappe.conf else None
    model = getattr(frappe.conf, "gemini_model", None) if frappe and hasattr(frappe, "conf") and frappe.conf else None
    if not model:
        model = DEFAULT_GEMINI_MODEL

    if not api_key:
        return rule_based_fallback_nlu(message_text, context_state)

    prompt = f"User Message: \"{message_text}\""
    if context_state and context_state.get("pending_action"):
        prompt += f"\nPrevious Context State: {json.dumps(context_state)}"

    # 1. Try Google GenAI official SDK first if installed
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=GEMINI_SYSTEM_PROMPT + "\n\n" + prompt,
            config={"response_mime_type": "application/json", "temperature": 0.1}
        )
        if response and response.text:
            text_out = response.text.strip()
            text_out = re.sub(r'^```json\s*', '', text_out, flags=re.MULTILINE)
            text_out = re.sub(r'```$', '', text_out, flags=re.MULTILINE).strip()
            parsed = json.loads(text_out)
            if not parsed.get("vehicle_number"):
                parsed["vehicle_number"] = extract_vehicle_pattern(message_text)
            if not parsed.get("parking_token"):
                parsed["parking_token"] = extract_token_pattern(message_text)
            return parsed
    except Exception:
        pass

    # 2. Try google.generativeai SDK if installed
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        m = genai.GenerativeModel(model)
        res = m.generate_content(GEMINI_SYSTEM_PROMPT + "\n\n" + prompt)
        if res and res.text:
            text_out = res.text.strip()
            text_out = re.sub(r'^```json\s*', '', text_out, flags=re.MULTILINE)
            text_out = re.sub(r'```$', '', text_out, flags=re.MULTILINE).strip()
            parsed = json.loads(text_out)
            if not parsed.get("vehicle_number"):
                parsed["vehicle_number"] = extract_vehicle_pattern(message_text)
            if not parsed.get("parking_token"):
                parsed["parking_token"] = extract_token_pattern(message_text)
            return parsed
    except Exception:
        pass

    # 3. Fall back to standard HTTP REST API call
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": GEMINI_SYSTEM_PROMPT + "\n\n" + prompt}]}],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }

    try:
        raw_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=raw_data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_body = json.loads(resp.read().decode('utf-8'))
            candidates = resp_body.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and "text" in parts[0]:
                    text_out = parts[0]["text"].strip()
                    text_out = re.sub(r'^```json\s*', '', text_out, flags=re.MULTILINE)
                    text_out = re.sub(r'```$', '', text_out, flags=re.MULTILINE).strip()
                    parsed = json.loads(text_out)
                    if not parsed.get("vehicle_number"):
                        parsed["vehicle_number"] = extract_vehicle_pattern(message_text)
                    if not parsed.get("parking_token"):
                        parsed["parking_token"] = extract_token_pattern(message_text)
                    return parsed
    except Exception as e:
        if frappe and hasattr(frappe, "log_error"):
            frappe.log_error(f"Gemini API NLU Error: {str(e)}")
    
    return rule_based_fallback_nlu(message_text, context_state)

def rule_based_fallback_nlu(text, context_state=None):
    """Rule-based NLU fallback when Gemini API key is absent or network fails."""
    t = str(text).strip().upper()
    v_no = extract_vehicle_pattern(text)
    token = extract_token_pattern(text)

    # Contextual follow-up check
    if context_state and context_state.get("pending_action") == "AWAITING_VEHICLE_NUMBER" and v_no:
        return {
            "intent": "FOLLOW_UP",
            "vehicle_number": v_no,
            "parking_token": token,
            "problem_description": None,
            "confidence": 0.95
        }

    # Greetings / Help
    if t in ["HI", "HELLO", "HEY", "GOOD MORNING", "GOOD EVENING", "HELP"]:
        return {"intent": "GREETING", "vehicle_number": None, "parking_token": None, "problem_description": None, "confidence": 0.98}

    # Out of scope questions
    out_words = ["WEATHER", "METRO", "JOKE", "ASSIGNMENT", "PRIME MINISTER", "NEWS", "SCORE"]
    if any(w in t for w in out_words):
        return {"intent": "OUT_OF_SCOPE", "vehicle_number": None, "parking_token": None, "problem_description": None, "confidence": 0.99}

    # Report problem
    prob_words = ["NOT ARRIVED", "HASN'T ARRIVED", "DELAYED", "PROBLEM", "COMPLAIN", "WRONG", "ISSUE", "DAMAGED", "NOT COMING"]
    if any(w in t for w in prob_words):
        return {"intent": "REPORT_PROBLEM", "vehicle_number": v_no, "parking_token": token, "problem_description": text, "confidence": 0.95}

    # Get my car
    get_words = ["BRING", "GET", "RETRIEVE", "FETCH", "WANT MY CAR", "NEED MY CAR", "TAKE MY CAR TO ENTRANCE", "WANT MY VEHICLE"]
    if any(w in t for w in get_words) or token:
        return {"intent": "GET_MY_CAR", "vehicle_number": v_no, "parking_token": token, "problem_description": None, "confidence": 0.95}

    # Park my car
    park_words = ["PARK", "VALET", "TAKE MY CAR FOR PARKING", "HERE TO PARK"]
    if any(w in t for w in park_words):
        return {"intent": "PARK_MY_CAR", "vehicle_number": v_no, "parking_token": token, "problem_description": None, "confidence": 0.95}

    # Check status
    status_words = ["STATUS", "WHERE IS MY CAR", "IS MY CAR PARKED", "WHERE IS MY VEHICLE"]
    if any(w in t for w in status_words):
        return {"intent": "CHECK_STATUS", "vehicle_number": v_no, "parking_token": token, "problem_description": None, "confidence": 0.95}

    # Standalone vehicle number
    if v_no and len(t) <= 15:
        return {"intent": "PARK_MY_CAR", "vehicle_number": v_no, "parking_token": token, "problem_description": None, "confidence": 0.90}

    return {"intent": "UNKNOWN", "vehicle_number": v_no, "parking_token": token, "problem_description": None, "confidence": 0.40}
