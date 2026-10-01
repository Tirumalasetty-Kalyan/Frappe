# Copyright (c) 2026, Valet Parking Team and contributors
# See license.txt

import copy
import time
import unittest
from valet_parking.valet_parking.doctype.parking_ticket.parking_ticket import ParkingTicket, VALID_STATUSES

try:
    from frappe.tests.utils import FrappeTestCase
except ImportError:
    FrappeTestCase = unittest.TestCase

def simulate_save(ticket):
    """Helper to simulate Frappe document lifecycle saving in standalone tests.
    Always calls before_insert() to set defaults (token, status, timestamps),
    because Frappe's is_new() returns False when __islocal is not in the
    constructor dict, which would skip before_insert() and leave status=None.
    """
    ticket.before_insert()
    ticket.validate()
    ticket._doc_before_save = copy.deepcopy(ticket)

class TestParkingTicket(FrappeTestCase):

    def test_ticket_creation_and_defaults(self):
        """Verify ticket creation, token generation, initial status, and uppercase formatting."""
        ticket = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1234567890",
            "vehicle_number": "ts09ea1234",
            "vehicle_type": "Car"
        })
        simulate_save(ticket)

        self.assertEqual(ticket.status, "Awaiting Parking")
        self.assertIsNotNone(ticket.token_number)
        self.assertTrue(ticket.token_number.startswith("VP-"))
        self.assertIsNotNone(ticket.created_at)
        self.assertEqual(ticket.vehicle_number, "TS09EA1234")

    def test_qr_code_whatsapp_url_generation(self):
        """Verify automatic generation of QR code with WhatsApp wa.me URL payload."""
        ticket = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1987654321",
            "vehicle_number": "KA05MH1111",
            "vehicle_type": "Car"
        })
        simulate_save(ticket)

        # 1. Verify qr_code field is set
        self.assertIsNotNone(ticket.qr_code)
        self.assertTrue(ticket.qr_code.startswith("data:image/svg+xml") or "<svg" in ticket.qr_code or "<img" in ticket.qr_code or "http" in ticket.qr_code)

        # 2. Verify wa.me URL payload structure
        payload_url = ticket.get_qr_payload_url()
        self.assertIn("https://wa.me/", payload_url)
        self.assertIn(ticket.token_number, payload_url)
        self.assertIn(ticket.get_valet_whatsapp_number(), payload_url)

    def test_valid_status_transitions_and_timestamps(self):
        """Verify step-by-step valid status transitions and timestamp recording."""
        ticket = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1987654321",
            "vehicle_number": "KA01AB9999",
            "vehicle_type": "SUV"
        })
        simulate_save(ticket)

        # Initial state: Awaiting Parking
        self.assertEqual(ticket.status, "Awaiting Parking")
        self.assertIsNotNone(ticket.created_at)
        self.assertIsNone(getattr(ticket, "parked_at", None))

        # Transition 1: Awaiting Parking -> Parked
        ticket.status = "Parked"
        simulate_save(ticket)
        self.assertIsNotNone(ticket.parked_at)

        # Transition 2: Parked -> Retrieval Requested
        ticket.status = "Retrieval Requested"
        simulate_save(ticket)
        self.assertIsNotNone(ticket.retrieval_requested_at)

        # Transition 3: Retrieval Requested -> On The Way
        ticket.status = "On The Way"
        simulate_save(ticket)
        self.assertIsNotNone(ticket.on_the_way_at)

        # Transition 4: On The Way -> Delivered
        ticket.status = "Delivered"
        simulate_save(ticket)
        self.assertIsNotNone(ticket.delivered_at)

    def test_invalid_status_transitions_rejected(self):
        """Verify server-side rejection of illegal status transitions."""
        t1 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V1"})
        simulate_save(t1)
        t1.status = "Retrieval Requested"
        with self.assertRaises(ValueError):
            t1.validate()

        t2 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V2"})
        simulate_save(t2)
        t2.status = "On The Way"
        with self.assertRaises(ValueError):
            t2.validate()

        t3 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V3"})
        simulate_save(t3)
        t3.status = "Delivered"
        with self.assertRaises(ValueError):
            t3.validate()

        t4 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V4"})
        simulate_save(t4)
        t4.status = "Parked"
        simulate_save(t4)
        t4.status = "On The Way"
        with self.assertRaises(ValueError):
            t4.validate()

        t5 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V5"})
        simulate_save(t5)
        t5.status = "Parked"
        simulate_save(t5)
        t5.status = "Delivered"
        with self.assertRaises(ValueError):
            t5.validate()

        t6 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V6"})
        simulate_save(t6)
        t6.status = "Parked"
        simulate_save(t6)
        t6.status = "Retrieval Requested"
        simulate_save(t6)
        t6.status = "Delivered"
        with self.assertRaises(ValueError):
            t6.validate()

        t7 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "111", "vehicle_number": "V7"})
        simulate_save(t7)
        t7.status = "Parked"
        simulate_save(t7)
        t7.status = "Retrieval Requested"
        simulate_save(t7)
        t7.status = "On The Way"
        simulate_save(t7)
        t7.status = "Delivered"
        simulate_save(t7)

        for illegal_status in ["Awaiting Parking", "Parked", "Retrieval Requested", "On The Way"]:
            t7.status = illegal_status
            with self.assertRaises(ValueError):
                t7.validate()

    def test_timestamps_not_overwritten_on_subsequent_saves(self):
        """Verify existing timestamps are preserved and not overwritten on re-saving."""
        ticket = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1234567890",
            "vehicle_number": "DL01XY1234"
        })
        simulate_save(ticket)
        ticket.status = "Parked"
        simulate_save(ticket)

        original_parked_at = ticket.parked_at
        self.assertIsNotNone(original_parked_at)

        simulate_save(ticket)
        self.assertEqual(ticket.parked_at, original_parked_at)

        ticket.status = "Retrieval Requested"
        simulate_save(ticket)
        self.assertEqual(ticket.parked_at, original_parked_at)

    def test_token_immutability(self):
        """Verify token_number cannot be modified after initial creation."""
        ticket = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1234567890",
            "vehicle_number": "MH12AB1234"
        })
        simulate_save(ticket)

        ticket.token_number = "VP-HACKED"
        with self.assertRaises(ValueError):
            ticket.validate()

    def test_required_fields_validation(self):
        """Verify mandatory fields trigger server-side validation errors when missing."""
        t1 = ParkingTicket({"doctype": "Parking Ticket", "vehicle_number": "MH12AB1234"})
        with self.assertRaises(ValueError):
            simulate_save(t1)

        t2 = ParkingTicket({"doctype": "Parking Ticket", "customer_whatsapp_number": "+1234567890"})
        with self.assertRaises(ValueError):
            simulate_save(t2)

        t3 = ParkingTicket({
            "doctype": "Parking Ticket",
            "customer_whatsapp_number": "+1234567890",
            "vehicle_number": "MH12AB1234",
            "status": "Unknown Status"
        })
        with self.assertRaises(ValueError):
            simulate_save(t3)

if __name__ == "__main__":
    unittest.main()
