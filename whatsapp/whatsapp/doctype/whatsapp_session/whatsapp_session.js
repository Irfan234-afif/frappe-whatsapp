frappe.ui.form.on('Whatsapp Session', {
    refresh: function(frm) {
        if (!frm.doc.__islocal) {
            frm.add_custom_button(__('Start Session'), function() {
                frappe.call({
                    doc: frm.doc,
                    method: 'start_session',
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            });

            frm.add_custom_button(__('Stop Session'), function() {
                frappe.call({
                    doc: frm.doc,
                    method: 'stop_session',
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __('Actions'));

            frm.add_custom_button(__('Get Status'), function() {
                frappe.call({
                    doc: frm.doc,
                    method: 'fetch_status',
                    callback: function(r) {
                        frm.reload_doc();
                    }
                });
            }, __('Actions'));
        }
    },
    qr_scan_button: function(frm) {
        // Create a dialog to show the QR code
        let qr_dialog = new frappe.ui.Dialog({
            title: __('Scan QR Code'),
            size: 'medium',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'qr_code_html'
                }
            ],
            primary_action_label: __('Close'),
            primary_action: function() {
                qr_dialog.hide();
            }
        });
        
        // Show loading state
        qr_dialog.fields_dict.qr_code_html.$wrapper.html(`
            <div class="text-center" style="padding: 20px;">
                <div class="spinner-border text-primary" role="status">
                    <span class="sr-only">${__('Getting QR Code...')}</span>
                </div>
                <p class="text-muted mt-3">${__('Generating QR Code...')}</p>
            </div>
        `);
        
        qr_dialog.show();
        
        // Fetch QR code
        frappe.call({
            doc: frm.doc,
            method: 'scan_qr',
            callback: function(r) {
                if (!r.exc && r.message) {
                    if (r.message.includes('<img')) {
                        // Successfully got QR code image
                        qr_dialog.fields_dict.qr_code_html.$wrapper.html(`
                            <div class="text-center" style="padding: 20px;">
                                <p class="text-muted mb-3">${__('Scan this QR code with WhatsApp on your phone')}</p>
                                ${r.message}
                                <div class="mt-3">
                                    <p class="text-info"><i class="fa fa-info-circle"></i> ${__('Current Status')}: <strong>${frm.doc.status || 'Unknown'}</strong></p>
                                </div>
                            </div>
                        `);
                        
                        // Auto-refresh status every 3 seconds to check if QR was scanned
                        let status_interval = setInterval(function() {
                            frappe.call({
                                doc: frm.doc,
                                method: 'fetch_status',
                                callback: function(status_r) {
                                    if (status_r.message === 'Connected') {
                                        clearInterval(status_interval);
                                        qr_dialog.fields_dict.qr_code_html.$wrapper.html(`
                                            <div class="text-center" style="padding: 40px;">
                                                <i class="fa fa-check-circle text-success" style="font-size: 60px;"></i>
                                                <h4 class="text-success mt-3">${__('Successfully Connected!')}</h4>
                                                <p class="text-muted">${__('Your WhatsApp session is now active')}</p>
                                            </div>
                                        `);
                                        frm.reload_doc();
                                        
                                        // Auto-close after 2 seconds
                                        setTimeout(function() {
                                            qr_dialog.hide();
                                        }, 2000);
                                    }
                                }
                            });
                        }, 3000);
                        
                        // Clear interval when dialog is closed
                        qr_dialog.onhide = function() {
                            clearInterval(status_interval);
                        };
                    } else {
                        // Error message from server
                        qr_dialog.fields_dict.qr_code_html.$wrapper.html(`
                            <div class="text-center" style="padding: 20px;">
                                <i class="fa fa-exclamation-triangle text-warning" style="font-size: 40px;"></i>
                                <p class="text-danger mt-3">${r.message}</p>
                            </div>
                        `);
                    }
                } else {
                    // Exception occurred
                    qr_dialog.fields_dict.qr_code_html.$wrapper.html(`
                        <div class="text-center" style="padding: 20px;">
                            <i class="fa fa-times-circle text-danger" style="font-size: 40px;"></i>
                            <p class="text-danger mt-3">${__('Error loading QR Code. Please try again.')}</p>
                        </div>
                    `);
                }
            }
        });
    }
});
