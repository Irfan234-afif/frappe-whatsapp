import frappe
from frappe.model.document import Document
from whatsapp.whatsapp.utils import get_provider
import json

class WhatsappSession(Document):
    def get_provider_instance(self):
        return get_provider(self)
    
    def get_friendly_status(self, api_status):
        """Map WAHA API status codes to user-friendly labels"""
        status_map = {
            "SCAN_QR_CODE": "Ready to Scan QR",
            "WORKING": "Connected",
            "STOPPED": "Disconnected",
            "FAILED": "Failed",
            "STARTING": "Starting...",
            "ERROR": "Failed"
        }
        return status_map.get(api_status, "Unknown")

    @frappe.whitelist()
    def start_session(self):
        provider = self.get_provider_instance()
        response = provider.start_session()
        self.response = json.dumps(response, indent=4)
        raw_status = provider.get_status()
        self.status = self.get_friendly_status(raw_status)
        self.save()
        return response

    def create_session(self, save_doc=True):
        provider = self.get_provider_instance()
        response = provider.create_session()
        self.response = json.dumps(response, indent=4)
        raw_status = provider.get_status()
        self.status = self.get_friendly_status(raw_status)
        if save_doc:
            self.save()
        return response

    @frappe.whitelist()
    def stop_session(self):
        provider = self.get_provider_instance()
        response = provider.stop_session()
        self.response = json.dumps(response, indent=4)
        raw_status = provider.get_status()
        self.status = self.get_friendly_status(raw_status)
        self.save()
        return response

    @frappe.whitelist()
    def scan_qr(self):
        try:
            provider = self.get_provider_instance()
            qr_code = provider.get_qr_code()
            # If qr_code is HTML image tag, save it.
            # Check if response is error string.
            if "<img" in qr_code:
                self.qr_code_image = qr_code
            else:
                self.qr_code_image = None
                self.response = json.dumps({"message": qr_code}, indent=4)
            
            self.save()
            return qr_code
        except Exception as e:
            return f"Error: {str(e)}"

    @frappe.whitelist()
    def fetch_status(self):
        provider = self.get_provider_instance()
        raw_status = provider.get_status()
        self.status = self.get_friendly_status(raw_status)
        self.save()
        return self.status

    def on_trash(self):
        """Delete session from WAHA when document is deleted"""
        try:
            provider = self.get_provider_instance()
            response = provider.delete_session()
            
            if response.get("error"):
                frappe.log_error(f"Error deleting WAHA session: {response.get('error')}", "WAHA Session Delete")
            else:
                frappe.msgprint(f"Session '{self.session_name}' deleted from WAHA successfully")
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "WAHA Session Delete Error")
            # Don't throw error - allow Frappe document deletion to continue even if WAHA delete fails

    def before_insert(self):
        self.create_session(save_doc=False)
