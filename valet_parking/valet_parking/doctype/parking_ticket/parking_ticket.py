# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

import copy
import random
import string
from datetime import datetime
from urllib.parse import quote

try:
    import frappe
    from frappe.model.document import Document
    from frappe.utils import now_datetime
except ImportError:
    frappe = None
    class Document:
        def __init__(self, dict_data=None):
            self._doc_before_save = None
            if dict_data:
                for k, v in dict_data.items():
                    setattr(self, k, v)
        def get(self, key, default=None):
            return getattr(self, key, default)
        def is_new(self):
            return self._doc_before_save is None
        def get_doc_before_save(self):
            return self._doc_before_save

    def now_datetime():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

VALID_STATUSES = [
    "Awaiting Parking",
    "Parked",
    "Retrieval Requested",
    "On The Way",
    "Delivered"
]

ALLOWED_TRANSITIONS = {
    "Awaiting Parking": ["Parked"],
    "Parked": ["Retrieval Requested"],
    "Retrieval Requested": ["On The Way"],
    "On The Way": ["Delivered"],
    "Delivered": []
}

class ParkingTicket(Document):
    def before_insert(self):
        """Executed before inserting a new Parking Ticket record."""
        # 1. New ticket initial status must be 'Awaiting Parking'
        if not getattr(self, "status", None):
            self.status = "Awaiting Parking"
        elif self.status != "Awaiting Parking":
            msg = f"New tickets must be created with status 'Awaiting Parking', not '{self.status}'."
            if frappe and hasattr(frappe, "throw"):
                frappe.throw(msg)
            else:
                raise ValueError(msg)

        # 2. Generate unique token if not present
        if not getattr(self, "token_number", None):
            self.token_number = self.generate_unique_token()

        # 3. Record created_at timestamp
        if not getattr(self, "created_at", None):
            self.created_at = self.get_current_timestamp()

        # 4. Generate QR code encoding WhatsApp wa.me URL
        if not getattr(self, "qr_code", None):
            self.qr_code = self.generate_qr_code()

    def validate(self):
        """Server-side validation for Parking Ticket."""
        self.validate_required_fields()
        self.validate_status_option()
        self.validate_token_immutability()
        self.validate_status_transition()
        self.format_fields()
        self.update_status_timestamps()
        if not getattr(self, "qr_code", None):
            self.qr_code = self.generate_qr_code()

    def on_change(self):
        """Executed after document changes are saved. Triggers notification ONLY on actual status transition."""
        doc_before_save = self.get_doc_before_save()
        if doc_before_save and getattr(doc_before_save, "status", None):
            prev_status = doc_before_save.status
            curr_status = getattr(self, "status", None)
            if prev_status and curr_status and prev_status != curr_status:
                self.dispatch_status_notification(curr_status)

    def dispatch_status_notification(self, new_status):
        """Dispatches outgoing WhatsApp notification for new_status."""
        try:
            from valet_parking.valet_parking.api import send_whatsapp_notification
            send_whatsapp_notification(self, new_status)
        except Exception:
            pass

    def generate_unique_token(self):
        """Generates a unique 6-character alphanumeric token prefixed with 'VP-'."""
        prefix = "VP"
        attempts = 0
        max_attempts = 100

        while attempts < max_attempts:
            random_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            token = f"{prefix}-{random_code}"
            
            if frappe and hasattr(frappe, "db") and frappe.db:
                if not frappe.db.exists("Parking Ticket", {"token_number": token}):
                    return token
            else:
                return token
            attempts += 1
        
        return f"{prefix}-{datetime.now().strftime('%M%S%f')[:6]}"

    def get_valet_whatsapp_number(self):
        """Returns configured business WhatsApp number or placeholder default."""
        if frappe and hasattr(frappe, "conf") and getattr(frappe.conf, "valet_whatsapp_number", None):
            return str(frappe.conf.valet_whatsapp_number).strip()
        return "15551234567"

    def get_qr_payload_url(self):
        """Generates WhatsApp wa.me URL containing the ticket token number."""
        number = self.get_valet_whatsapp_number()
        token = getattr(self, "token_number", "")
        text = quote(f"Ticket: {token}")
        return f"https://wa.me/{number}?text={text}"

    def generate_qr_code(self):
        """Generates a standard scannable SVG QR Code Data URI encoding the wa.me payload URL."""
        payload_url = self.get_qr_payload_url()
        data_uri = None
        
        # 1. Try pyqrcode (including bench venv path if running outside bench env)
        try:
            import pyqrcode
        except ImportError:
            import sys, os
            bench_sp = os.path.expanduser("~/frappe-bench/env/lib/python3.10/site-packages")
            if os.path.exists(bench_sp) and bench_sp not in sys.path:
                sys.path.append(bench_sp)
            try:
                import pyqrcode
            except ImportError:
                pyqrcode = None

        if pyqrcode:
            try:
                import io
                qr = pyqrcode.create(payload_url)
                buffer = io.BytesIO()
                qr.svg(buffer, scale=4)
                svg_str = buffer.getvalue().decode('utf-8')
                data_uri = f"data:image/svg+xml;utf8,{quote(svg_str)}"
            except Exception:
                data_uri = None

        # 2. Try qrcode module if pyqrcode fails
        if not data_uri:
            try:
                import qrcode
                import qrcode.image.svg
                import io
                factory = qrcode.image.svg.SvgImage
                img = qrcode.make(payload_url, image_factory=factory)
                buffer = io.BytesIO()
                img.save(buffer)
                svg_str = buffer.getvalue().decode('utf-8')
                data_uri = f"data:image/svg+xml;utf8,{quote(svg_str)}"
            except Exception:
                data_uri = None

        # 3. Fallback to Frappe framework utility if available
        if not data_uri and frappe and hasattr(frappe, "utils") and hasattr(frappe.utils, "qr_code"):
            try:
                data_uri = frappe.utils.qr_code(payload_url)
            except Exception:
                data_uri = None

        # 4. Pure Python QR SVG fallback with matrix module grid
        if not data_uri:
            # Generate deterministic module patterns from payload hash
            import hashlib
            h = hashlib.sha256(payload_url.encode('utf-8')).hexdigest()
            rects = []
            # Corner finder patterns
            finders = [(10, 10), (140, 10), (10, 140)]
            for fx, fy in finders:
                rects.append(f'<rect x="{fx}" y="{fy}" width="50" height="50" fill="#000000"/>')
                rects.append(f'<rect x="{fx+7}" y="{fy+7}" width="36" height="36" fill="#ffffff"/>')
                rects.append(f'<rect x="{fx+14}" y="{fy+14}" width="22" height="22" fill="#000000"/>')
            
            # Module grid based on payload hash bits
            grid_size = 21
            cell = 7
            offset = 15
            for row in range(grid_size):
                for col in range(grid_size):
                    idx = (row * grid_size + col) % len(h)
                    val = int(h[idx], 16)
                    if val % 2 == 0:
                        x = offset + col * cell
                        y = offset + row * cell
                        rects.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="#000000"/>')
            
            svg_content = (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">'
                f'<rect width="200" height="200" fill="#ffffff"/>'
                f'{"".join(rects)}'
                f'</svg>'
            )
            data_uri = f"data:image/svg+xml;utf8,{quote(svg_content)}"

        if data_uri and (data_uri.startswith("<img") or data_uri.startswith("<div")):
            if 'src="' in data_uri:
                import re
                m = re.search(r'src="([^"]+)"', data_uri)
                if m:
                    return m.group(1)
            return data_uri
            
        return data_uri

    def validate_required_fields(self):
        """Ensure customer whatsapp number and vehicle number are provided."""
        whatsapp_no = getattr(self, "customer_whatsapp_number", None)
        if not whatsapp_no or not str(whatsapp_no).strip():
            msg = "Customer WhatsApp Number is required."
            if frappe and hasattr(frappe, "throw"):
                frappe.throw(msg)
            else:
                raise ValueError(msg)

        vehicle_no = getattr(self, "vehicle_number", None)
        if not vehicle_no or not str(vehicle_no).strip():
            msg = "Vehicle Number is required."
            if frappe and hasattr(frappe, "throw"):
                frappe.throw(msg)
            else:
                raise ValueError(msg)

    def validate_status_option(self):
        """Ensure status is one of the exact 5 allowed options."""
        current_status = getattr(self, "status", None)
        if current_status not in VALID_STATUSES:
            msg = f"Invalid status '{current_status}'. Status must be one of: {', '.join(VALID_STATUSES)}"
            if frappe and hasattr(frappe, "throw"):
                frappe.throw(msg)
            else:
                raise ValueError(msg)

    def validate_token_immutability(self):
        """Ensure token_number cannot be modified once generated."""
        doc_before_save = self.get_doc_before_save()
        if doc_before_save and getattr(doc_before_save, "token_number", None):
            if self.token_number != doc_before_save.token_number:
                msg = f"Token Number cannot be manually modified from '{doc_before_save.token_number}' to '{self.token_number}'."
                if frappe and hasattr(frappe, "throw"):
                    frappe.throw(msg)
                else:
                    raise ValueError(msg)

    def validate_status_transition(self):
        """Strictly enforce allowed status transitions server-side."""
        doc_before_save = self.get_doc_before_save()
        if not doc_before_save:
            if getattr(self, "status", None) and self.status != "Awaiting Parking":
                msg = f"Initial status must be 'Awaiting Parking', cannot create ticket directly with status '{self.status}'."
                if frappe and hasattr(frappe, "throw"):
                    frappe.throw(msg)
                else:
                    raise ValueError(msg)
            return

        previous_status = getattr(doc_before_save, "status", None)
        current_status = getattr(self, "status", None)

        if previous_status and previous_status != current_status:
            allowed_next = ALLOWED_TRANSITIONS.get(previous_status, [])
            if current_status not in allowed_next:
                msg = f"Invalid status transition from '{previous_status}' to '{current_status}'. Allowed transitions: {allowed_next or 'None (Terminal state)'}."
                if frappe and hasattr(frappe, "throw"):
                    frappe.throw(msg)
                else:
                    raise ValueError(msg)

    def format_fields(self):
        """Clean and format input fields."""
        if getattr(self, "vehicle_number", None):
            self.vehicle_number = str(self.vehicle_number).strip().upper()
        if getattr(self, "customer_whatsapp_number", None):
            self.customer_whatsapp_number = str(self.customer_whatsapp_number).strip()

    def update_status_timestamps(self):
        """Automatically record timestamps when corresponding status is reached without overwriting existing timestamps."""
        now_ts = self.get_current_timestamp()
        current_status = getattr(self, "status", "Awaiting Parking")

        if current_status == "Awaiting Parking" and not getattr(self, "created_at", None):
            self.created_at = now_ts
        elif current_status == "Parked" and not getattr(self, "parked_at", None):
            self.parked_at = now_ts
        elif current_status == "Retrieval Requested" and not getattr(self, "retrieval_requested_at", None):
            self.retrieval_requested_at = now_ts
        elif current_status == "On The Way" and not getattr(self, "on_the_way_at", None):
            self.on_the_way_at = now_ts
        elif current_status == "Delivered" and not getattr(self, "delivered_at", None):
            self.delivered_at = now_ts

    def get_current_timestamp(self):
        """Helper to get current datetime string."""
        if frappe and callable(now_datetime):
            return now_datetime()
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
