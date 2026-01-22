# Copyright (c) 2026, Irfan Afifi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


from frappe.core.utils import html2text

class WhatsappTemplate(Document):
	def get_message(self, context):
		message = frappe.render_template(self.message, context)
		return html2text(message)
