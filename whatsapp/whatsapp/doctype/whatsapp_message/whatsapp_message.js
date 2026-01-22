// Copyright (c) 2026, Irfan Afifi and contributors
// For license information, please see license.txt

frappe.ui.form.on("Whatsapp Message", {
	refresh(frm) {
		if (frm.doc.status === "Failed") {
			frm.add_custom_button(__("Retry"), function() {
				frm.call({
					method: "retry",
					doc: frm.doc,
					callback: function(r) {
						if (!r.exc) {
							frappe.msgprint(__("Message retried"));
							frm.reload_doc();
						}
					}
				});
			});
		}
	},
});
