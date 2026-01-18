import requests
import json
import frappe
from urllib.parse import quote
import base64
from whatsapp.whatsapp.services.provider import WhatsappProvider

class WAHAProvider(WhatsappProvider):
    def __init__(self, session_doc):
        super().__init__(session_doc)
        self.settings = frappe.get_single("Whatsapp Settings")

    def get_headers(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        api_key = self.settings.get_password("api_key")
        if api_key:
            headers["X-Api-Key"] = api_key
        return headers

    def get_url(self, endpoint):
        base_url = self.settings.api_url or "http://localhost:3000"
        return f"{base_url}/api/{endpoint}"

    def create_session(self):
        """Create a new WAHA session using POST /api/sessions"""
        # Get webhook URL for this site
        webhook_url = frappe.utils.get_url("/api/method/whatsapp.whatsapp.api.webhook.handle_waha_webhook")
        
        payload = {
            "name": self.session_doc.session_name,
            "config": {
                "proxy": None,
                "webhooks": [
                    {
                        "url": webhook_url,
                        "events": ["message.any", "session.status"],
                        "hmac": None,
                        "retries": None,
                        "customHeaders": None
                    }
                ]
            }
        }
        try:
            frappe.errprint(f"Creating WAHA session with payload: {json.dumps(payload)}")
            response = requests.post(self.get_url("sessions"), json=payload, headers=self.get_headers())
            frappe.errprint(f"WAHA Create Response {response.status_code}: {response.text}")
            try:
                return response.json()
            except Exception:
                # WAHA returns 201 Created on success, sometimes with empty body
                if response.status_code == 201:
                    return {"name": self.session_doc.session_name, "message": "Session created"}
                    
                # Handle cases where response is not valid JSON
                error_msg = f"WAHA API Error ({response.status_code}): {response.text}"
                frappe.log_error(error_msg, "WAHA Session Create Error")
                frappe.throw(error_msg)
                
        except Exception as e:
            frappe.log_error(f"Error creating WAHA session", e)
            frappe.throw(f"Error creating Whatsapp session: {str(e)}")

    def start_session(self):
        """Start an existing WAHA session using POST /api/sessions/{name}/start"""
        try:
            name = quote(self.session_doc.session_name)
            response = requests.post(
                self.get_url(f"sessions/{name}/start"),
                headers=self.get_headers()
            )
            try:
                return response.json()
            except Exception:
                if response.status_code in [200, 201, 204]:
                    return {"message": "Session started"}
                return {"error": f"WAHA API Error ({response.status_code}): {response.text}"}
        except Exception as e:
            frappe.log_error(f"Error starting WAHA session: {str(e)}")
            return {"error": str(e)}

    def stop_session(self):
        """Stop an existing WAHA session using POST /api/sessions/{name}/stop"""
        try:
            name = quote(self.session_doc.session_name)
            response = requests.post(
                self.get_url(f"sessions/{name}/stop"),
                headers=self.get_headers()
            )
            try:
                return response.json()
            except Exception:
                if response.status_code in [200, 201, 204]:
                    return {"message": "Session stopped"}
                return {"error": f"WAHA API Error ({response.status_code}): {response.text}"}
        except Exception as e:
            return {"error": str(e)}

    def delete_session(self):
        """Delete a WAHA session using DELETE /api/sessions/{name}"""
        try:
            name = quote(self.session_doc.session_name)
            response = requests.delete(
                self.get_url(f"sessions/{name}"),
                headers=self.get_headers()
            )
            try:
                return response.json()
            except Exception:
                if response.status_code in [200, 201, 204]:
                    return {"success": True}
                return {"error": f"WAHA API Error ({response.status_code}): {response.text}"}
        except Exception as e:
            frappe.log_error(f"Error deleting WAHA session: {str(e)}")
            return {"error": str(e)}

    def get_qr_code(self):
        """Get QR code from WAHA using GET /api/sessions/{name}/auth/qr"""
        try:
            # Try to start the session (WAHA will handle if already started)
            self.start_session()

            # Use the correct auth/qr endpoint instead of screenshot
            name = quote(self.session_doc.session_name)
            url = self.get_url(f"{name}/auth/qr")
            headers = self.get_headers()
            # Add Accept header to receive image directly
            headers["Accept"] = "image/png"

            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # The endpoint returns binary image by default
                encoded_string = base64.b64encode(response.content).decode('utf-8')
                return f'<img src="data:image/png;base64,{encoded_string}" style="max-width: 300px;">'
            
            try:
                error_msg = response.json().get('message', response.text)
            except Exception:
                error_msg = response.text

            frappe.throw(error_msg)
            
        except Exception as e:
            frappe.log_error("Waha Error", e)
            frappe.throw(e)

    def get_status(self):
        try:
            response = requests.get(
                self.get_url("sessions"), 
                params={"all": "true"}, 
                headers=self.get_headers()
            )
            if response.status_code == 200:
                sessions = response.json()
                # find our session
                for session in sessions:
                    if session.get('name') == self.session_doc.session_name:
                        return session.get('status')
                return "STOPPED" # If not found, assume stopped
            return "UNKNOWN"
        except Exception as e:
            return "ERROR"

    def send_message_api(self, to_number, message):
        payload = {
            "session": self.session_doc.session_name,
            "chatId": f"{to_number}@c.us", # Assuming standard format, might need adjustment
            "text": message
        }
        try:
            response = requests.post(self.get_url("sendText"), json=payload, headers=self.get_headers())
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def send_message(self, to_number, message, message_id=None):
        frappe.enqueue(
            "whatsapp.whatsapp.services.waha.send_waha_message_job",
            queue="short",
            session_name=self.session_doc.session_name,
            to_number=to_number,
            message=message,
            message_id=message_id,
            enqueue_after_commit=True
        )
        return {"id": "Queued", "status": "Queued"}

def send_waha_message_job(session_name, to_number, message, message_id=None):
    try:
        session_doc = frappe.get_doc("Whatsapp Session", session_name)
        provider = WAHAProvider(session_doc)
        response = provider.send_message_api(to_number, message)
        
        if message_id:
            msg_doc = frappe.get_doc("Whatsapp Message", message_id)
            msg_doc.response = json.dumps(response, indent=4)
            
            if isinstance(response, dict) and response.get('id'):
                msg_doc.status = "Sent"
                provider_msg_id = response.get('id')
                if isinstance(provider_msg_id, dict):
                    msg_doc.message_id = provider_msg_id.get('_serialized') or provider_msg_id.get('id')
                else:
                    msg_doc.message_id = provider_msg_id
            else:
                msg_doc.status = "Failed"
            
            msg_doc.save()
            frappe.db.commit()
            
    except Exception as e:
        frappe.log_error(f"Error in send_waha_message_job", e)
        if message_id:
            try:
                frappe.db.set_value("Whatsapp Message", message_id, {
                    "status": "Failed",
                    "response": str(e)
                })
                frappe.db.commit()
            except Exception:
                frappe.log_error("Failed to update Whatsapp Message status")

        raise e
