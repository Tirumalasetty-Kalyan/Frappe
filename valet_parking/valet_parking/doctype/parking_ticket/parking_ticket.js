// Copyright (c) 2026, Valet Parking Team and contributors
// For license information, please see license.txt

frappe.ui.form.on('Parking Ticket', {
    refresh: function(frm) {
        // Render WhatsApp QR Code in HTML display field
        if (!frm.is_new() && frm.doc.qr_code) {
            let qr_data = frm.doc.qr_code;
            let img_src = qr_data;

            // Extract src URL/data-URI if qr_data is wrapped in an HTML <img> tag
            if (qr_data.includes('src="')) {
                let match = qr_data.match(/src="([^"]+)"/);
                if (match) {
                    img_src = match[1];
                }
            }

            let qr_html = `
                <div class="whatsapp-qr-container text-center p-3 my-2" style="max-width: 260px; border: 1px solid #d1d8dd; border-radius: 8px; background-color: #f8f9fa;">
                    <h5 class="mb-3 font-weight-bold" style="color: #1c2b36; font-size: 15px;">WhatsApp QR Code</h5>
                    <img src="${img_src}" alt="WhatsApp QR Code" style="width: 200px; height: 200px; object-fit: contain; display: block; margin: 0 auto; border-radius: 4px;" />
                </div>
            `;

            if (frm.fields_dict.qr_code_html && frm.fields_dict.qr_code_html.$wrapper) {
                frm.fields_dict.qr_code_html.$wrapper.html(qr_html);
            }
        }

        // Quick status transition action buttons in Frappe Desk UI
        if (!frm.is_new()) {
            if (frm.doc.status === "Awaiting Parking") {
                frm.add_custom_button(__('Mark as Parked'), function() {
                    frm.set_value('status', 'Parked');
                    frm.save();
                }).addClass('btn-primary');
            } else if (frm.doc.status === "Parked") {
                frm.add_custom_button(__('Request Retrieval'), function() {
                    frm.set_value('status', 'Retrieval Requested');
                    frm.save();
                }).addClass('btn-warning');
            } else if (frm.doc.status === "Retrieval Requested") {
                frm.add_custom_button(__('Mark On The Way'), function() {
                    frm.set_value('status', 'On The Way');
                    frm.save();
                }).addClass('btn-info');
            } else if (frm.doc.status === "On The Way") {
                frm.add_custom_button(__('Mark Delivered'), function() {
                    frm.set_value('status', 'Delivered');
                    frm.save();
                }).addClass('btn-success');
            }
        }
    }
});
