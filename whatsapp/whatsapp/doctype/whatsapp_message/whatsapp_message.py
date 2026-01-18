import frappe
from frappe.model.document import Document
import json

class WhatsappMessage(Document):
    def after_insert(self):
        if not self.whatsapp_session:
            frappe.throw("Whatsapp Session is required to send message")
        
        session_doc = frappe.get_doc("Whatsapp Session", self.whatsapp_session)
        provider = session_doc.get_provider_instance()
        
        # Pass message_id so backround job can update the document
        response = provider.send_message(self.to_number, self.message, message_id=self.name)
        self.response = json.dumps(response, indent=4)
        
        # Check success based on provider response
        if response.get('status') == 'Queued':
             self.status = "Queued"
             self.message_id = "Queued"
        elif isinstance(response, dict) and response.get('id'):
            self.status = "Sent"
            msg_id = response.get('id')
            if isinstance(msg_id, dict):
                self.message_id = msg_id.get('_serialized') or msg_id.get('id')
            else:
                self.message_id = msg_id
        else:
            self.status = "Failed"
        
        self.db_set('status', self.status)
        self.db_set('response', self.response)
        self.db_set('message_id', self.message_id)

