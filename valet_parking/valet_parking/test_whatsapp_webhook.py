# Copyright (c) 2026, Valet Parking Team and contributors
# See license.txt

import hmac
import hashlib
import json
import unittest
from unittest.mock import MagicMock, patch
from valet_parking.valet_parking.api import handle_whatsapp_webhook, validate_webhook_signature, extract_vehicle_number, send_whatsapp_message, get_webhook_secret

try:
    import frappe
    from frappe.tests.utils import FrappeTestCase
except ImportError:
    frappe = None
    FrappeTestCase = unittest.TestCase

# Vehicle numbers and phone numbers used exclusively by these tests.
# setUp deletes any residual active tickets before each test.
_TEST_VEHICLES = [
    "TS09EA7777", "KA01AB9999", "MH12AB5555", "DL08CD1234",
    "MH02CD4444", "UP32AB1111", "TS09EA8888", "TS09AB8888",
]
_TEST_PHONES = [
    "15559998888", "15558887777", "15553334444", "15556667777",
    "15554443333", "15552221111", "15550009999", "919988776655",
]
ACTIVE_STATUSES = ["Awaiting Parking", "Parked", "Retrieval Requested", "On The Way"]


class TestWhatsAppWebhook(FrappeTestCase):

    def setUp(self):
        super().setUp()
        if frappe and hasattr(frappe, "get_all"):
            for vehicle in _TEST_VEHICLES:
                tickets = frappe.get_all(
                    "Parking Ticket",
                    filters={"vehicle_number": vehicle, "status": ["in", ACTIVE_STATUSES]},
                    fields=["name"]
                )
                for t in tickets:
                    frappe.delete_doc("Parking Ticket", t.name, ignore_permissions=True, force=True)
            frappe.db.commit()

    def test_extract_vehicle_number(self):
        """Verify regex extraction of vehicle numbers from message text."""
        self.assertEqual(extract_vehicle_number("Park my vehicle TS09EA1234 please"), "TS09EA1234")
        self.assertEqual(extract_vehicle_number("KA05MH1111"), "KA05MH1111")
        self.assertEqual(extract_vehicle_number("DL01C1234"), "DL01C1234")

    def test_get_webhook_verification(self):
        """Verify GET webhook challenge verification for Meta setup returns raw challenge string with HTTP 200."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        frappe.request = MagicMock()
        frappe.request.method = "GET"
        frappe.request.args = {
            "hub.mode": "subscribe",
            "hub.verify_token": get_webhook_secret(),
            "hub.challenge": "987654321"
        }
        frappe.response = {}

        res = handle_whatsapp_webhook()
        self.assertEqual(res, "987654321")
        # api.py GET handler sets type='download' for plain-text challenge response
        self.assertEqual(frappe.response.get("type"), "download")
        self.assertEqual(frappe.response.get("result"), "987654321")
        self.assertEqual(frappe.response.get("http_status_code"), 200)

    def test_post_meta_cloud_api_webhook_ticket_creation(self):
        """Verify POST Meta Cloud API payload extracts sender/vehicle and creates ticket with status Awaiting Parking."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        meta_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WHATSAPP_ACC_ID",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "messages": [
                                    {
                                        "from": "+15559998888",
                                        "id": "wamid.12345",
                                        "timestamp": "1670000000",
                                        "text": {
                                            "body": "Please park my vehicle TS09EA7777 at valet"
                                        },
                                        "type": "text"
                                    }
                                ]
                            },
                            "field": "messages"
                        }
                    ]
                }
            ]
        }

        raw_data = json.dumps(meta_payload).encode('utf-8')
        frappe.request = MagicMock()
        frappe.request.method = "POST"
        frappe.request.get_data.return_value = raw_data
        frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}
        frappe.request.args = {}

        res = handle_whatsapp_webhook()
        self.assertEqual(res.get("status"), "success")

        ticket_info = res.get("ticket", {})
        self.assertEqual(ticket_info.get("status"), "Awaiting Parking")
        self.assertEqual(ticket_info.get("customer_whatsapp_number"), "+15559998888")
        self.assertEqual(ticket_info.get("vehicle_number"), "TS09EA7777")
        self.assertTrue(str(ticket_info.get("token_number")).startswith("VP-"))

    def test_post_direct_payload_ticket_creation(self):
        """Verify POST direct payload creates ticket and triggers token/QR generation."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        direct_payload = {
            "from": "+15558887777",
            "vehicle_number": "KA01AB9999"
        }

        raw_data = json.dumps(direct_payload).encode('utf-8')
        frappe.request = MagicMock()
        frappe.request.method = "POST"
        frappe.request.get_data.return_value = raw_data
        frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}
        frappe.request.args = {}

        res = handle_whatsapp_webhook()
        self.assertEqual(res.get("status"), "success")

        ticket_info = res.get("ticket", {})
        self.assertEqual(ticket_info.get("status"), "Awaiting Parking")
        self.assertEqual(ticket_info.get("customer_whatsapp_number"), "+15558887777")
        self.assertEqual(ticket_info.get("vehicle_number"), "KA01AB9999")

    def test_post_unauthorized_signature_rejected(self):
        """Verify POST request with invalid signature/token is rejected."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        # Temporarily mock secret to enforce verification
        frappe.conf.whatsapp_webhook_secret = "secret_production_token"
        try:
            raw_data = json.dumps({"from": "123", "vehicle_number": "V1"}).encode('utf-8')
            frappe.request = MagicMock()
            frappe.request.method = "POST"
            frappe.request.get_data.return_value = raw_data
            frappe.request.headers = {"X-Webhook-Token": "invalid_hacker_token"}
            frappe.request.args = {}
            frappe.response = {}

            res = handle_whatsapp_webhook()
            self.assertEqual(res.get("status"), "error")
            self.assertIn("Invalid or missing", res.get("message"))
            self.assertEqual(frappe.response.get("http_status_code"), 401)
        finally:
            frappe.conf.whatsapp_webhook_secret = None

    def test_all_status_transition_notifications(self):
        """Verify WhatsApp notifications sent on Parked, Retrieval Requested, On The Way, and Delivered transitions."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        frappe.flags.sent_whatsapp_messages = []

        def _mock_send(to_number, text):
            """Intercept send_whatsapp_message to always use simulation logger during tests."""
            import re as _re
            cleaned = _re.sub(r'[^0-9+]', '', str(to_number).strip())
            entry = {"status": "simulated", "to": cleaned, "text": text}
            if not hasattr(frappe.flags, "sent_whatsapp_messages") or frappe.flags.sent_whatsapp_messages is None:
                frappe.flags.sent_whatsapp_messages = []
            frappe.flags.sent_whatsapp_messages.append(entry)
            return entry

        with patch("valet_parking.valet_parking.api.send_whatsapp_message", side_effect=_mock_send):
            # 1. Create ticket
            doc = frappe.get_doc({
                "doctype": "Parking Ticket",
                "customer_whatsapp_number": "+15553334444",
                "vehicle_number": "MH12AB5555",
                "vehicle_type": "Car",
                "status": "Awaiting Parking"
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

            # 2. Transition: Awaiting Parking -> Parked
            doc.status = "Parked"
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(len(messages) >= 1, f"Expected >= 1 message after Parked transition, got {len(messages)}")
            self.assertIn("safely parked", messages[-1]["text"])
            self.assertIn("MH12AB5555", messages[-1]["text"])

            # 3. Transition: Parked -> Retrieval Requested
            doc.status = "Retrieval Requested"
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertIn("Retrieval request received", messages[-1]["text"])

            # 4. Transition: Retrieval Requested -> On The Way
            doc.status = "On The Way"
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertIn("on the way to the pickup point", messages[-1]["text"])

            # 5. Transition: On The Way -> Delivered
            doc.status = "Delivered"
            doc.save(ignore_permissions=True)
            frappe.db.commit()

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertIn("has been delivered", messages[-1]["text"])

    def test_get_my_car_webhook_transition(self):
        """Verify incoming 'Get My Car' webhook transitions Parked ticket to Retrieval Requested."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        # Use number WITHOUT '+' to match bot_engine's clean_sender normalization
        # (api.py passes sender as-is from Meta, bot_engine strips '+' for storage/lookup)
        customer_no = "15556667777"
        doc = frappe.get_doc({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": customer_no,
            "vehicle_number": "DL08CD1234",
            "vehicle_type": "Car",
            "status": "Awaiting Parking"
        })
        doc.insert(ignore_permissions=True)
        doc.status = "Parked"
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        # 2. Simulate incoming WhatsApp POST message: "Get My Car"
        raw_data = json.dumps({"from": customer_no, "message": "Get My Car"}).encode('utf-8')
        frappe.request = MagicMock()
        frappe.request.method = "POST"
        frappe.request.get_data.return_value = raw_data
        frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}
        frappe.request.args = {}

        res = handle_whatsapp_webhook()
        self.assertEqual(res.get("status"), "success")
        doc.reload()
        self.assertEqual(doc.status, "Retrieval Requested")

    def test_meta_interactive_button_reply_webhook(self):
        """Verify Meta Cloud API interactive button reply 'Get My Car' transitions ticket from Parked to Retrieval Requested."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        # Use number WITHOUT '+' to match bot_engine's clean_sender normalization
        customer_no = "15554443333"
        doc = frappe.get_doc({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": customer_no,
            "vehicle_number": "MH02CD4444",
            "vehicle_type": "Car",
            "status": "Awaiting Parking"
        })
        doc.insert(ignore_permissions=True)
        doc.status = "Parked"
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        interactive_payload = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "ACC_ID",
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": customer_no,
                            "id": "wamid.btn.1",
                            "type": "interactive",
                            "interactive": {
                                "type": "button_reply",
                                "button_reply": {
                                    "id": f"btn_get_car_{doc.token_number}",
                                    "title": "Get My Car"
                                }
                            }
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        raw_data = json.dumps(interactive_payload).encode('utf-8')
        frappe.request = MagicMock()
        frappe.request.method = "POST"
        frappe.request.get_data.return_value = raw_data
        frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}
        frappe.request.args = {}

        res = handle_whatsapp_webhook()
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res.get("ticket", {}).get("status"), "Retrieval Requested")

        doc.reload()
        self.assertEqual(doc.status, "Retrieval Requested")

    def test_no_duplicate_notification_on_unrelated_save(self):
        """Verify no duplicate notification is sent when doc is saved without status change."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        doc = frappe.get_doc({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+15552221111",
            "vehicle_number": "UP32AB1111",
            "status": "Awaiting Parking"
        })
        doc.insert(ignore_permissions=True)
        doc.status = "Parked"
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        initial_count = len(getattr(frappe.flags, "sent_whatsapp_messages", []))

        # Re-save without changing status
        doc.save(ignore_permissions=True)
        frappe.db.commit()

        new_count = len(getattr(frappe.flags, "sent_whatsapp_messages", []))
        self.assertEqual(initial_count, new_count)

    def test_end_to_end_full_valet_lifecycle(self):
        """Complete E2E MVP test: Webhook ticket creation -> Parked -> Get My Car webhook -> Retrieval Requested -> On The Way -> Delivered."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        frappe.flags.sent_whatsapp_messages = []
        # bot_engine strips '+' from sender numbers; store/compare without '+'
        customer_no = "15550009999"
        vehicle_no = "TS09EA8888"

        def _mock_send(to_number, text):
            import re as _re
            cleaned = _re.sub(r'[^0-9+]', '', str(to_number).strip())
            entry = {"status": "simulated", "to": cleaned, "text": text}
            if not hasattr(frappe.flags, "sent_whatsapp_messages") or frappe.flags.sent_whatsapp_messages is None:
                frappe.flags.sent_whatsapp_messages = []
            frappe.flags.sent_whatsapp_messages.append(entry)
            return entry

        with patch("valet_parking.valet_parking.api.send_whatsapp_message", side_effect=_mock_send):
            # STEP 1: Incoming WhatsApp Webhook (Create Parking Ticket)
            meta_payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "ACC_ID",
                    "changes": [{
                        "value": {
                            "messages": [{
                                "from": customer_no,
                                "id": "wamid.e2e.1",
                                "timestamp": "1670000001",
                                "text": {"body": f"Please park my car {vehicle_no}"},
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
            frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}
            frappe.request.args = {}

            res = handle_whatsapp_webhook()
            self.assertEqual(res.get("status"), "success")
            ticket_info = res.get("ticket", {})
            ticket_name = ticket_info.get("name")
            token_number = ticket_info.get("token_number")
            self.assertEqual(ticket_info.get("status"), "Awaiting Parking")
            self.assertTrue(token_number.startswith("VP-"))

            # Reload document from database
            ticket = frappe.get_doc("Parking Ticket", ticket_name)
            # bot_engine normalizes numbers (strips '+'), compare stripped values
            self.assertEqual(ticket.customer_whatsapp_number.lstrip('+'), customer_no.lstrip('+'))
            self.assertEqual(ticket.vehicle_number, vehicle_no)
            self.assertIsNotNone(ticket.created_at)
            self.assertIsNotNone(ticket.qr_code)

            # STEP 2: Transition to 'Parked' & Verify Parked Notification
            ticket.status = "Parked"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            ticket.reload()
            self.assertEqual(ticket.status, "Parked")
            self.assertIsNotNone(ticket.parked_at)

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(len(messages) >= 1, f"Expected >= 1 message after Parked, got {len(messages)}")
            self.assertIn("safely parked", messages[-1]["text"])
            self.assertIn(token_number, messages[-1]["text"])

            # STEP 3: Incoming "Get My Car" Webhook -> Transition to 'Retrieval Requested'
            retrieval_payload = {"from": customer_no, "message": "Get My Car"}
            raw_data = json.dumps(retrieval_payload).encode('utf-8')
            frappe.request = MagicMock()
            frappe.request.method = "POST"
            frappe.request.get_data.return_value = raw_data
            frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}

            res_retrieval = handle_whatsapp_webhook()
            self.assertEqual(res_retrieval.get("status"), "success")

            ticket.reload()
            self.assertEqual(ticket.status, "Retrieval Requested")
            self.assertIsNotNone(ticket.retrieval_requested_at)

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(any("Retrieval request received" in m["text"] for m in messages))

            # STEP 4: Transition to 'On The Way' & Verify Notification
            ticket.status = "On The Way"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            ticket.reload()
            self.assertEqual(ticket.status, "On The Way")
            self.assertIsNotNone(ticket.on_the_way_at)

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(any("on the way to the pickup point" in m["text"] for m in messages))

            # STEP 5: Transition to 'Delivered' & Verify Notification
            ticket.status = "Delivered"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            ticket.reload()
            self.assertEqual(ticket.status, "Delivered")
            self.assertIsNotNone(ticket.delivered_at)

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(any("has been delivered" in m["text"] for m in messages))

    def test_e2e_whatsapp_lifecycle_via_bot_engine(self):
        """Regression Test: E2E lifecycle via natural language Gemini bot engine webhook path."""
        if not frappe:
            self.skipTest("Frappe framework not imported")

        frappe.flags.sent_whatsapp_messages = []
        customer_no = "919988776655"

        def _mock_send(to_number, text):
            import re as _re
            cleaned = _re.sub(r'[^0-9+]', '', str(to_number).strip())
            entry = {"status": "simulated", "to": cleaned, "text": text}
            if not hasattr(frappe.flags, "sent_whatsapp_messages") or frappe.flags.sent_whatsapp_messages is None:
                frappe.flags.sent_whatsapp_messages = []
            frappe.flags.sent_whatsapp_messages.append(entry)
            return entry

        with patch("valet_parking.valet_parking.api.send_whatsapp_message", side_effect=_mock_send):
            # 1. Incoming natural language park request
            meta_payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "ACC_123",
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [{
                                "from": customer_no,
                                "id": "wmid.e2e_bot_1",
                                "timestamp": "1726320000",
                                "text": {"body": "Hi, please park my car TS09AB8888"},
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
            frappe.request.headers = {"X-Webhook-Token": get_webhook_secret()}

            res = handle_whatsapp_webhook()
            self.assertEqual(res.get("status"), "success")
            ticket_info = res.get("ticket", {})
            ticket_name = ticket_info.get("name")
            self.assertIsNotNone(ticket_name)
            self.assertEqual(ticket_info.get("vehicle_number"), "TS09AB8888")

            ticket = frappe.get_doc("Parking Ticket", ticket_name)
            self.assertEqual(ticket.status, "Awaiting Parking")

            # 2. Transition to Parked & Verify Notification
            ticket.status = "Parked"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            messages = getattr(frappe.flags, "sent_whatsapp_messages", [])
            self.assertTrue(len(messages) >= 1, f"Expected >= 1 message after Parked, got {len(messages)}")
            self.assertIn("safely parked", messages[-1]["text"])

            # 3. Natural language Get My Car request
            get_car_payload = {
                "object": "whatsapp_business_account",
                "entry": [{
                    "id": "ACC_123",
                    "changes": [{
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [{
                                "from": customer_no,
                                "id": "wmid.e2e_bot_2",
                                "timestamp": "1726320005",
                                "text": {"body": "Can you please bring my car now?"},
                                "type": "text"
                            }]
                        },
                        "field": "messages"
                    }]
                }]
            }

            frappe.request.get_data.return_value = json.dumps(get_car_payload).encode('utf-8')
            res_get = handle_whatsapp_webhook()
            self.assertEqual(res_get.get("status"), "success")

            ticket.reload()
            self.assertEqual(ticket.status, "Retrieval Requested")

            # 4. Transition to On The Way & Delivered
            ticket.status = "On The Way"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            ticket.status = "Delivered"
            ticket.save(ignore_permissions=True)
            frappe.db.commit()

            ticket.reload()
            self.assertEqual(ticket.status, "Delivered")

if __name__ == "__main__":
    unittest.main()

