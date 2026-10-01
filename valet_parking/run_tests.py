import sys
import unittest

# Ensure current workspace root is in PYTHONPATH
sys.path.insert(0, ".")

def main():
    print("=" * 60)
    print(" Running Unit Tests for Valet Parking App (DocType, Dashboard, PWA & Webhook)")
    print("=" * 60)
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    ticket_suite = loader.loadTestsFromName("valet_parking.valet_parking.doctype.parking_ticket.test_parking_ticket")
    dashboard_suite = loader.loadTestsFromName("valet_parking.valet_parking.page.valet_dashboard.test_valet_dashboard")
    pwa_suite = loader.loadTestsFromName("valet_parking.test_pwa_manifest")
    webhook_suite = loader.loadTestsFromName("valet_parking.valet_parking.test_whatsapp_webhook")
    
    suite.addTests(ticket_suite)
    suite.addTests(dashboard_suite)
    suite.addTests(pwa_suite)
    suite.addTests(webhook_suite)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\n" + "=" * 60)
        print(" SUCCESS: All Valet Parking backend, PWA & Webhook tests passed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print(" FAILURE: Unit tests failed.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
