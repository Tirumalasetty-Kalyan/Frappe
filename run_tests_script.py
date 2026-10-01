import unittest
import sys
import os

import frappe

# Initialize site context
frappe.init('valet.local')
frappe.connect()
frappe.set_user('Administrator')

# Setup sys.path for test discovery
sys.path.insert(0, '/home/varshini_boda/frappe-bench/apps/valet_parking/valet_parking/valet_parking')
sys.path.insert(0, '/home/varshini_boda/frappe-bench/apps/valet_parking/valet_parking')
sys.path.insert(0, '/home/varshini_boda/frappe-bench/apps/valet_parking')

from valet_parking.valet_parking.test_whatsapp_webhook import TestWhatsAppWebhook
from valet_parking.valet_parking.test_gemini_bot import TestGeminiBot
from valet_parking.valet_parking.doctype.parking_ticket.test_parking_ticket import TestParkingTicket
from valet_parking.valet_parking.page.valet_dashboard.test_valet_dashboard import TestValetDashboard
from valet_parking.test_pwa_manifest import TestPWAManifest

suite = unittest.TestSuite()

print("Loading TestWhatsAppWebhook (including E2E lifecycle regression test)...")
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestWhatsAppWebhook))

print("Loading TestGeminiBot (all 19 NLU bot tests)...")
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestGeminiBot))

print("Loading TestParkingTicket...")
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestParkingTicket))

print("Loading TestValetDashboard...")
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestValetDashboard))

print("Loading TestPWAManifest...")
suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestPWAManifest))

print(f"\n=======================================================")
print(f"RUNNING COMPLETE UNIT TEST SUITE ({suite.countTestCases()} TESTS TOTAL)")
print(f"=======================================================\n")

runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print("\n=======================================================")
print(f"TEST RESULTS SUMMARY:")
print(f"Total Tests Run: {result.testsRun}")
print(f"Failures: {len(result.failures)}")
print(f"Errors: {len(result.errors)}")
print(f"Was Successful: {result.wasSuccessful()}")
print(f"=======================================================\n")

sys.exit(0 if result.wasSuccessful() else 1)
