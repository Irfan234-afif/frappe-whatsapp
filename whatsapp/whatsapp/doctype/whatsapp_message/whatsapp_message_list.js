frappe.listview_settings["Whatsapp Message"] = {
	get_indicator: function (doc) {
		if (doc.status === "Sent") {
			return [__("Sent"), "green", "status,=,Sent"];
		} else if (doc.status === "Delivered") {
			return [__("Delivered"), "green", "status,=,Delivered"];
		} else if (doc.status === "Read") {
			return [__("Read"), "green", "status,=,Read"];
		} else if (doc.status === "Failed") {
			return [__("Failed"), "red", "status,=,Failed"];
		} else if (doc.status === "Queued") {
			return [__("Queued"), "orange", "status,=,Queued"];
		}
	},
};
