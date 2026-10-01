# Copyright (c) 2026, Valet Parking Team and contributors
# See license.txt

import unittest
from unittest.mock import patch, MagicMock

from valet_parking.gemini_nlu import parse_gemini_intent, rule_based_fallback_nlu
from valet_parking.conversation_memory import get_conversation_state, set_conversation_state, clear_conversation_state
from valet_parking.bot_engine import process_customer_message

try:
    import frappe
    from frappe.tests.utils import FrappeTestCase
except ImportError:
    frappe = None
    FrappeTestCase = unittest.TestCase

# Vehicle numbers used exclusively by this test suite.
# setUp deletes any pre-existing active tickets for these vehicles to avoid
# "already exists" false failures when the test database is reused.
_TEST_VEHICLES = [
    "TS09AB1234", "TS09AB9999", "TS09CD1111", "TS09EA5555",
    "TS09EA6666", "TS09EA9999", "TS09EA4444",
    "KA01AB1111", "KA01AB2222",
]

# Phone numbers used exclusively by this test suite.
_TEST_PHONES = [
    "919876543210", "918888899999",
    "917777766666", "917777755555",
]

ACTIVE_STATUSES = ["Awaiting Parking", "Parked", "Retrieval Requested", "On The Way"]


def _cleanup_test_data():
    """Delete test tickets and clear conversation states before each test."""
    if frappe and hasattr(frappe, "get_all"):
        for vehicle in _TEST_VEHICLES:
            tickets = frappe.get_all(
                "Parking Ticket",
                filters={"vehicle_number": vehicle, "status": ["in", ACTIVE_STATUSES]},
                fields=["name"]
            )
            for t in tickets:
                frappe.delete_doc("Parking Ticket", t.name, ignore_permissions=True, force=True)
        if hasattr(frappe, "db"):
            frappe.db.commit()

    for phone in _TEST_PHONES:
        clear_conversation_state(phone)

class TestGeminiBot(FrappeTestCase):

    def setUp(self):
        super().setUp()
        _cleanup_test_data()

    # 1. Greeting
    def test_greeting(self):
        res = process_customer_message("919876543210", "Hi")
        self.assertIn("Welcome to Valet Parking", res.get("reply", ""))

    # 2. Park with vehicle number
    def test_park_with_vehicle_number(self):
        res = process_customer_message("919876543210", "I need to park my car TS09AB1234")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("TS09AB1234", res.get("reply", ""))
        self.assertIn("ticket", res)

    # 3. Park without vehicle number
    def test_park_without_vehicle_number(self):
        res = process_customer_message("919876543210", "I want to park my car")
        self.assertIn("Please send your vehicle number", res.get("reply", ""))
        state = get_conversation_state("919876543210")
        self.assertEqual(state.get("pending_action"), "AWAITING_VEHICLE_NUMBER")

    # 4. Follow-up vehicle number
    def test_follow_up_vehicle_number(self):
        process_customer_message("919876543210", "I want to park my car")
        res = process_customer_message("919876543210", "TS09AB1234")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("TS09AB1234", res.get("reply", ""))

    # 5. Natural get-my-car wording
    def test_natural_get_my_car_wording(self):
        # Create parked ticket first
        park_res = process_customer_message("919876543210", "Park TS09EA5555")
        ticket_name = park_res["ticket"]["name"]
        if frappe:
            ticket_doc = frappe.get_doc("Parking Ticket", ticket_name)
            ticket_doc.status = "Parked"
            ticket_doc.save(ignore_permissions=True)

        res = process_customer_message("919876543210", "Can you please bring my car to the entrance?")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("Retrieval request received", res.get("reply", ""))

    # 6. Natural status question
    def test_natural_status_question(self):
        process_customer_message("919876543210", "Park TS09EA6666")
        res = process_customer_message("919876543210", "Where is my car?")
        self.assertIn("Vehicle Status", res.get("reply", ""))

    # 7. Natural complaint / report problem
    def test_natural_complaint(self):
        res = process_customer_message("919876543210", "My car hasn't arrived yet and it's delayed")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("issue has been reported", res.get("reply", ""))

    # 8. Ambiguous message
    def test_ambiguous_message(self):
        res = process_customer_message("919876543210", "my car")
        self.assertIn("what would you like me to do", res.get("reply", ""))

    # 9. Unrelated question (out of scope)
    def test_unrelated_question(self):
        res = process_customer_message("919876543210", "What is the weather today in Hyderabad?")
        self.assertIn("I can help only with valet parking services", res.get("reply", ""))

    # 10. Spelling mistake
    def test_spelling_mistake(self):
        res = process_customer_message("919876543210", "pls park dis vehicle TS09AB9999")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("TS09AB9999", res.get("reply", ""))

    # 11. Informal wording
    def test_informal_wording(self):
        res = process_customer_message("919876543210", "yo I need valet for TS09CD1111")
        self.assertEqual(res.get("status"), "success")
        self.assertIn("TS09CD1111", res.get("reply", ""))

    # 12. Mixed Indian-English phrasing
    def test_mixed_indian_english(self):
        res = process_customer_message("919876543210", "bhai bring my vehicle TS09AB1234")
        self.assertIn("reply", res)

    # 13. Low confidence response
    # Patch the name as it is used inside bot_engine (where it was imported).
    def test_low_confidence_response(self):
        with patch('valet_parking.bot_engine.parse_gemini_intent') as mock_nlu:
            mock_nlu.return_value = {"intent": "GET_MY_CAR", "confidence": 0.50}
            res = process_customer_message("919876543210", "maybe get it?")
            self.assertIn("what would you like me to do", res.get("reply", ""))

    # 14. Invalid Gemini JSON
    # Use a message that is not a greeting and not keyword-matched, so the mock fires.
    def test_invalid_gemini_json(self):
        with patch('valet_parking.bot_engine.parse_gemini_intent') as mock_nlu:
            mock_nlu.side_effect = ValueError("Invalid JSON from Gemini")
            res = process_customer_message("919876543210", "zxqpvbrm floptop 99999")
            self.assertIn("couldn't understand", res.get("reply", ""))

    # 15. Gemini API timeout
    # Use a message that is not a greeting so the mock fires before short-circuit.
    def test_gemini_timeout(self):
        with patch('valet_parking.bot_engine.parse_gemini_intent') as mock_nlu:
            mock_nlu.side_effect = TimeoutError("Gemini API Timeout")
            res = process_customer_message("919876543210", "zxqpvbrm floptop 99999")
            self.assertIn("couldn't understand", res.get("reply", ""))

    # 16. Multiple active tickets
    def test_multiple_active_tickets(self):
        p1 = process_customer_message("918888899999", "Park KA01AB1111")
        p2 = process_customer_message("918888899999", "Park KA01AB2222")
        if frappe:
            doc1 = frappe.get_doc("Parking Ticket", p1["ticket"]["name"])
            doc1.status = "Parked"
            doc1.save(ignore_permissions=True)

            doc2 = frappe.get_doc("Parking Ticket", p2["ticket"]["name"])
            doc2.status = "Parked"
            doc2.save(ignore_permissions=True)

        res = process_customer_message("918888899999", "Bring my car")
        self.assertIn("multiple parked vehicles", res.get("reply", ""))

    # 17. Unknown ticket lookup
    def test_unknown_ticket(self):
        res = process_customer_message("910000000000", "Get my car")
        self.assertIn("No active parked vehicle found", res.get("reply", ""))

    # 18. Full multi-turn parking conversation
    def test_full_multi_turn_parking_conversation(self):
        r1 = process_customer_message("917777766666", "I want to park my vehicle")
        self.assertIn("Please send your vehicle number", r1.get("reply", ""))

        r2 = process_customer_message("917777766666", "TS09EA9999")
        self.assertEqual(r2.get("status"), "success")
        self.assertIn("TS09EA9999", r2.get("reply", ""))

    # 19. Full multi-turn retrieval conversation
    def test_full_multi_turn_retrieval_conversation(self):
        p = process_customer_message("917777755555", "Park TS09EA4444")
        if frappe:
            d = frappe.get_doc("Parking Ticket", p["ticket"]["name"])
            d.status = "Parked"
            d.save(ignore_permissions=True)

        r = process_customer_message("917777755555", "Can you bring my car?")
        self.assertEqual(r.get("status"), "success")
        self.assertIn("Retrieval request received", r.get("reply", ""))
