# Copyright (c) 2026, Valet Parking Team and contributors
# See license.txt

import json
import os
import unittest

class TestPWAManifest(unittest.TestCase):
    def test_manifest_file_validity(self):
        """Verify manifest.json exists, parses cleanly, and contains PWA properties."""
        manifest_path = os.path.join(
            os.path.dirname(__file__), "public", "manifest.json"
        )
        self.assertTrue(os.path.exists(manifest_path), f"Manifest file missing at {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data.get("name"), "Valet Parking")
        self.assertEqual(data.get("short_name"), "Valet")
        self.assertEqual(data.get("start_url"), "/app/valet-dashboard")
        self.assertEqual(data.get("display"), "standalone")
        self.assertEqual(data.get("theme_color"), "#17a2b8")

        icons = data.get("icons", [])
        self.assertGreaterEqual(len(icons), 2)
        sizes = [i.get("sizes") for i in icons]
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)

    def test_pwa_icon_files_exist(self):
        """Verify icon PNG files exist on disk."""
        public_dir = os.path.join(os.path.dirname(__file__), "public")
        icon192 = os.path.join(public_dir, "images", "icon-192.png")
        icon512 = os.path.join(public_dir, "images", "icon-512.png")

        self.assertTrue(os.path.exists(icon192), f"Missing 192x192 icon at {icon192}")
        self.assertTrue(os.path.exists(icon512), f"Missing 512x512 icon at {icon512}")

if __name__ == "__main__":
    unittest.main()
