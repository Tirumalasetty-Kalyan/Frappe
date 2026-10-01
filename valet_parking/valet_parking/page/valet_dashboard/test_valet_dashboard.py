# Copyright (c) 2026, Valet Parking Team and contributors
# See license.txt

import unittest
from valet_parking.valet_parking.page.valet_dashboard.valet_dashboard import (
    get_dashboard_summary,
    get_active_tickets,
    update_ticket_status
)
from valet_parking.valet_parking.doctype.parking_ticket.parking_ticket import ParkingTicket, VALID_STATUSES

try:
    from frappe.tests.utils import FrappeTestCase
except ImportError:
    FrappeTestCase = unittest.TestCase

class TestValetDashboard(FrappeTestCase):

    def test_dashboard_summary_fallback(self):
        """Verify summary returns dict with expected 4 active status keys."""
        summary = get_dashboard_summary()
        self.assertIn("Awaiting Parking", summary)
        self.assertIn("Parked", summary)
        self.assertIn("Retrieval Requested", summary)
        self.assertIn("On The Way", summary)

    def test_get_active_tickets_fallback(self):
        """Verify active tickets function returns list."""
        tickets = get_active_tickets()
        self.assertIsInstance(tickets, list)

    def test_update_ticket_status_validation(self):
        """Verify required parameters and framework checks in update_ticket_status."""
        with self.assertRaises(Exception):
            update_ticket_status("", "")

if __name__ == "__main__":
    unittest.main()
