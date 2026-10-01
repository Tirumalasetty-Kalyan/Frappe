# Copyright (c) 2026, Valet Parking Team and contributors
# For license information, please see license.txt

try:
    import frappe
    from frappe.model.document import Document
except ImportError:
    frappe = None
    class Document:
        def __init__(self, dict_data=None):
            if dict_data:
                for k, v in dict_data.items():
                    setattr(self, k, v)
        def insert(self, *args, **kwargs):
            return self
        def save(self, *args, **kwargs):
            return self

class ValetProblemReport(Document):
    def before_insert(self):
        if not getattr(self, "status", None):
            self.status = "Open"
