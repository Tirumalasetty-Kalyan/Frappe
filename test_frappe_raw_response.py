import frappe
import frappe.utils.response

frappe.init(site="valet.local")
frappe.connect()

frappe.response = frappe._dict()
frappe.response["type"] = "download"
frappe.response["content_type"] = "text/plain"
frappe.response["display_content_as"] = "inline"
frappe.response["filename"] = "challenge.txt"
frappe.response["filecontent"] = "987654321"
frappe.response["http_status_code"] = 200

res = frappe.utils.response.build_response()
print("BUILD RESPONSE RESULT:")
print("Status:", res.status)
print("Content-Type:", res.mimetype)
print("Headers:\n", res.headers)
print("Data Body:", res.get_data(as_text=True))
