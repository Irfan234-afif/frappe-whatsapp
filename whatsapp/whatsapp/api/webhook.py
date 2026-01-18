import frappe
import json
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_waha_webhook():
	"""
	Webhook endpoint to receive events from WAHA
	Handles message.any and session.status events
	"""
	try:
		# Get the request data
		data = frappe.request.get_json()
		
		if not data:
			frappe.log_error("No data received in webhook", "WAHA Webhook Error")
			return {"status": "error", "message": "No data received"}
		
		# Log the webhook event for debugging
		frappe.log_error(json.dumps(data, indent=2), "WAHA Webhook Received")
		
		event = data.get("event")
		session_name = data.get("session")
		payload = data.get("payload", {})
		
		if not event or not session_name:
			return {"status": "error", "message": "Missing event or session"}
		
		# Handle different event types
		if event == "message.any":
			handle_message_event(session_name, payload)
		elif event == "session.status":
			handle_session_status_event(session_name, payload)
		else:
			frappe.log_error(f"Unhandled event type: {event}", "WAHA Webhook")
		
		return {"status": "success"}
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "WAHA Webhook Error")
		return {"status": "error", "message": str(e)}


def handle_message_event(session_name, payload):
	"""
	Handle incoming message events
	Store message in Whatsapp Message DocType
	"""
	try:
		# Extract message details
		message_id = payload.get("id")
		from_number = payload.get("from", "")
		to_number = payload.get("to", "")
		body = payload.get("body", "")
		timestamp = payload.get("timestamp")
		has_media = payload.get("hasMedia", False)
		
		# Determine direction (incoming vs outgoing)
		# If 'from' contains @c.us it's from a contact (incoming)
		# If 'fromMe' is True, it's outgoing
		from_me = payload.get("fromMe", False)
		direction = "Outgoing" if from_me else "Incoming"
		
		# Only create record for incoming messages to avoid duplicates
		# (outgoing messages are already created when sent)
		if direction == "Incoming":
			# Check if message already exists
			existing = frappe.db.exists("Whatsapp Message", {"message_id": message_id})
			if existing:
				return
			
			# Get the session
			session = frappe.db.exists("Whatsapp Session", {"session_name": session_name})
			if not session:
				frappe.log_error(f"Session not found: {session_name}", "WAHA Webhook")
				return
			
			# Create new message record
			message_doc = frappe.get_doc({
				"doctype": "Whatsapp Message",
				"message_id": message_id,
				"whatsapp_session": session,
				"to_number": to_number if not from_me else from_number,
				"message": body,
				"status": "Delivered",  # Incoming messages are already delivered
				"response": json.dumps(payload, indent=2)
			})
			message_doc.insert(ignore_permissions=True)
			frappe.db.commit()
			
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "WAHA Message Handler Error")


def handle_session_status_event(session_name, payload):
	"""
	Handle session status change events
	Update Whatsapp Session status
	"""
	try:
		status = payload.get("status")
		if not status:
			return
		
		# Get the session document
		session = frappe.db.exists("Whatsapp Session", {"session_name": session_name})
		if not session:
			frappe.log_error(f"Session not found: {session_name}", "WAHA Webhook")
			return
		
		# Update session status
		session_doc = frappe.get_doc("Whatsapp Session", session)
		session_doc.status = session_doc.get_friendly_status(status)
		session_doc.save(ignore_permissions=True)
		frappe.db.commit()
		
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "WAHA Session Status Handler Error")
