# Copyright (c) 2026, Irfan Afifi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from typing import List, Union


class WhatsappNotification(Document):
	def validate(self):
		"""Validate the notification configuration"""
		if not self.recipients:
			frappe.throw("At least one recipient must be added")
	
	def send_notification(self, doc):
		"""
		Send WhatsApp notification for the given document
		
		Args:
			doc: The document that triggered the notification
		"""
		frappe.logger().warning(f"[WhatsApp Debug] send_notification called for {self.name}, doc: {doc.doctype} {doc.name}")
		
		# Check if notification is enabled
		if not self.enabled:
			frappe.logger().warning(f"[WhatsApp Debug] Notification {self.name} is disabled, skipping")
			return
		
		# Evaluate condition if specified
		if self.condition:
			frappe.logger().warning(f"[WhatsApp Debug] Evaluating condition for {self.name}: {self.condition}")
			if not self.evaluate_condition(doc):
				frappe.logger().warning(f"[WhatsApp Debug] Condition NOT met for {self.name} on {doc.doctype} {doc.name}")
				return
			frappe.logger().warning(f"[WhatsApp Debug] Condition MET for {self.name} on {doc.doctype} {doc.name}")
		
		# Generate reference_id if template is provided
		reference_id = None
		if self.reference_id_template:
			frappe.logger().warning(f"[WhatsApp Debug] Generating reference_id from template: {self.reference_id_template}")
			reference_id = self.generate_reference_id(doc)
			frappe.logger().warning(f"[WhatsApp Debug] Generated reference_id: {reference_id}")
			
			# Check for duplicate
			if reference_id and self.check_duplicate_reference(reference_id):
				frappe.logger().warning(f"[WhatsApp Debug] DUPLICATE found for reference_id: {reference_id}, skipping")
				return
			else:
				frappe.logger().warning(f"[WhatsApp Debug] No duplicate for reference_id: {reference_id}, proceeding")
		
		# Get all recipients
		frappe.logger().warning(f"[WhatsApp Debug] Getting recipients for {self.name}")
		recipients = self.get_recipients(doc)
		frappe.logger().warning(f"[WhatsApp Debug] Found {len(recipients) if recipients else 0} recipients: {recipients}")
		if not recipients:
			frappe.logger().warning(f"[WhatsApp Debug] NO RECIPIENTS found for {doc.doctype} {doc.name}, cannot send notification")
			return
		
		# Get WhatsApp session
		session = self.whatsapp_session or self.get_default_session()
		if not session:
			frappe.throw("No WhatsApp session available. Please configure a session or set a default active session.")
		
		# Get template
		template = frappe.get_doc("Whatsapp Template", self.whatsapp_template)
		
		# Prepare message with template variables replaced
		message = self.prepare_message(doc, template)
		
		# Send to all recipients
		for recipient in recipients:
			try:
				self.send_whatsapp_message(session, recipient, message, template, reference_id)
				frappe.logger().warning(f"WhatsApp sent to {recipient} for {doc.doctype} {doc.name}")
			except Exception as e:
				frappe.log_error(
					title=f"WhatsApp Notification Failed: {self.name}",
					message=f"Failed to send to {recipient}: {str(e)}\nDocument: {get_link_to_form(doc.doctype, doc.name)}"
				)
	
	def evaluate_condition(self, doc) -> bool:
		"""
		Evaluate the condition expression
		
		Args:
			doc: The document context
			
		Returns:
			bool: True if condition is met, False otherwise
		"""
		try:
			# Log relevant field values for debugging
			if "per_billed" in self.condition:
				per_billed_value = getattr(doc, "per_billed", None)
				frappe.logger().warning(f"[WhatsApp Debug] doc.per_billed = {per_billed_value} (type: {type(per_billed_value).__name__})")
				
				# Handle None value to prevent TypeError
				if per_billed_value is None:
					frappe.logger().warning(f"[WhatsApp Debug] per_billed is None, condition will fail")
					return False
			
			# Create safe evaluation context
			context = {
				"doc": doc,
				"frappe": frappe,
			}
			result = bool(frappe.safe_eval(self.condition, eval_locals=context))
			frappe.logger().warning(f"[WhatsApp Debug] Condition '{self.condition}' evaluated to: {result}")
			return result
		except Exception as e:
			frappe.log_error(
				title=f"WhatsApp Notification Condition Error: {self.name}",
				message=f"Error evaluating condition: {str(e)}\nCondition: {self.condition}"
			)
			return False
	
	def get_recipients(self, doc) -> List[str]:
		"""
		Get all recipients for the notification
		
		Args:
			doc: The document to extract recipients from
			
		Returns:
			List[str]: List of mobile numbers
		"""
		recipients = []
		
		for recipient_row in self.recipients:
			try:
				mobile_numbers = self.resolve_recipient(doc, recipient_row)
				
				# Handle both single strings and lists
				if isinstance(mobile_numbers, str):
					if mobile_numbers:
						recipients.append(mobile_numbers)
				elif isinstance(mobile_numbers, list):
					recipients.extend([num for num in mobile_numbers if num])
				
			except Exception as e:
				frappe.log_error(
					title=f"WhatsApp Notification Recipient Error: {self.name}",
					message=f"Error resolving recipient: {str(e)}\nRecipient config: {recipient_row.as_dict()}"
				)
		
		# Remove duplicates and empty values
		recipients = list(set([r.strip() for r in recipients if r and r.strip()]))
		
		return recipients
	
	def resolve_recipient(self, doc, recipient_row) -> Union[str, List[str]]:
		"""
		Resolve recipient based on the recipient type
		
		Args:
			doc: The document context
			recipient_row: The recipient configuration row
			
		Returns:
			str or List[str]: Mobile number(s)
		"""
		if recipient_row.recruit_by == "Field Path":
			return self.resolve_field_path(doc, recipient_row.field_path)
		
		elif recipient_row.recruit_by == "Python Expression":
			return self.resolve_python_expression(doc, recipient_row.python_expression)
		
		elif recipient_row.recruit_by == "Fixed Number":
			return recipient_row.fixed_number
		
		return None
	
	def resolve_field_path(self, doc, field_path: str) -> str:
		"""
		Resolve field path using dot notation
		
		Args:
			doc: The document to start from
			field_path: Path like "mobile_no" or "customer.mobile_no"
			
		Returns:
			str: The resolved value
		"""
		if not field_path:
			return None
		
		# Split path by dots
		parts = field_path.strip().split(".")
		current_value = doc
		
		for part in parts:
			if not current_value:
				return None
			
			# Get the value
			if isinstance(current_value, Document):
				current_value = current_value.get(part)
			elif isinstance(current_value, dict):
				current_value = current_value.get(part)
			else:
				return None
			
			# If it's a Link field and we have more parts to traverse, fetch the linked doc
			if current_value and len(parts) > 1 and parts.index(part) < len(parts) - 1:
				# Try to determine if this is a link field
				if isinstance(doc, Document):
					meta = frappe.get_meta(doc.doctype)
					field_meta = meta.get_field(part)
					
					if field_meta and field_meta.fieldtype == "Link" and field_meta.options:
						# Fetch the linked document
						try:
							current_value = frappe.get_doc(field_meta.options, current_value)
						except Exception:
							return None
		
		return current_value if isinstance(current_value, str) else str(current_value) if current_value else None
	
	def resolve_python_expression(self, doc, expression: str) -> Union[str, List[str]]:
		"""
		Evaluate Python expression to get recipient(s)
		
		Args:
			doc: The document context
			expression: Python expression to evaluate
			
		Returns:
			str or List[str]: Mobile number(s)
		"""
		if not expression:
			return None
		
		try:
			# Create safe evaluation context
			context = {
				"doc": doc,
				"frappe": frappe,
			}
			
			result = frappe.safe_eval(expression, eval_locals=context)
			return result
		
		except Exception as e:
			frappe.log_error(
				title=f"WhatsApp Notification Python Expression Error: {self.name}",
				message=f"Error evaluating expression: {str(e)}\nExpression: {expression}"
			)
			return None
	
	def prepare_message(self, doc, template) -> str:
		"""
		Prepare message by replacing template variables
		
		Args:
			doc: The document context
			template: The WhatsApp template
			
		Returns:
			str: The prepared message
		"""
		
		context = {
			"doc": doc,
			"frappe": frappe,
		}
		
		return template.get_message(context)
	
	def generate_reference_id(self, doc) -> str:
		"""
		Generate reference ID from template
		
		Args:
			doc: The document context
			
		Returns:
			str: Generated reference ID or None if error
		"""
		if not self.reference_id_template:
			return None
		
		try:
			# Use Jinja templating
			from frappe.utils.jinja import render_template
			
			context = {
				"doc": doc,
				"frappe": frappe,
			}
			
			reference_id = render_template(self.reference_id_template, context)
			return reference_id.strip() if reference_id else None
			
		except Exception as e:
			frappe.log_error(
				title=f"WhatsApp Notification Reference ID Error: {self.name}",
				message=f"Error generating reference_id: {str(e)}\nTemplate: {self.reference_id_template}"
			)
			return None
	
	def check_duplicate_reference(self, reference_id: str) -> bool:
		"""
		Check if a message with this reference_id already exists
		
		Args:
			reference_id: The reference ID to check
			
		Returns:
			bool: True if duplicate exists, False otherwise
		"""
		if not reference_id:
			return False
		
		# Query for existing message with this reference_id
		existing = frappe.db.exists(
			"Whatsapp Message",
			{"reference_id": reference_id}
		)
		
		return bool(existing)

	
	def send_whatsapp_message(self, session: str, recipient: str, message: str, template, reference_id: str = None, doc: Document = None):
		"""
		Send WhatsApp message using the session
		
		Args:
			session: WhatsApp session name
			recipient: Mobile number
			message: Message to send
			template: Template document
			reference_id: Optional reference ID for duplicate checking
		"""
		# Create WhatsApp Message document
		whatsapp_message = frappe.get_doc({
			"doctype": "Whatsapp Message",
			"whatsapp_session": session,
			"to_number": recipient,
			"message": message,
			"reference_id": reference_id,
			"reference_doctype": doc.doctype if doc else None,
			"reference_name": doc.name if doc else None,
		})
		whatsapp_message.insert(ignore_permissions=True)
		frappe.db.commit()
	
	def get_default_session(self) -> str:
		"""Get the default active WhatsApp session"""
		session = frappe.db.get_value(
			"Whatsapp Session",
			{"is_default_outgoing": 1},
			"name",
			order_by="modified desc"
		)
		return session


def trigger_whatsapp_notifications(doc, method=None):
	"""
	Trigger WhatsApp notifications for the given document and method
	
	Args:
		doc: The document that triggered the event
		method: The event method (e.g., "on_submit", "on_update")
	"""
	frappe.logger().warning(f"[WhatsApp Debug] trigger_whatsapp_notifications called for {doc.doctype} {doc.name}, method: {method}")
	
	# Map method to event name
	event_map = {
		"after_insert": "New",
		"on_update": "Save",
		"on_submit": "Submit",
		"on_cancel": "Cancel",
		"on_trash": "Delete",
		"on_update_after_submit": "Update After Submit",
	}
	
	event = event_map.get(method, "Save")
	frappe.logger().warning(f"[WhatsApp Debug] Looking for notifications with doctype={doc.doctype}, event={event}")
	
	# Get all enabled notifications for this doctype and event
	notifications = frappe.get_all(
		"Whatsapp Notification",
		filters={
			"enabled": 1,
			"document_type": doc.doctype,
			"event": event,
		},
		pluck="name"
	)
	
	frappe.logger().warning(f"[WhatsApp Debug] Found {len(notifications)} notifications: {notifications}")
	
	# Trigger each notification
	for notification_name in notifications:
		try:
			frappe.logger().warning(f"[WhatsApp Debug] Processing notification: {notification_name}")
			notification = frappe.get_doc("Whatsapp Notification", notification_name)
			notification.send_notification(doc)
			frappe.logger().warning(f"[WhatsApp Debug] Completed processing notification: {notification_name}")
		except Exception as e:
			frappe.logger().error(f"[WhatsApp Debug] ERROR in notification {notification_name}: {str(e)}")
			frappe.log_error(
				title=f"WhatsApp Notification Error: {notification_name}",
				message=f"Error sending notification: {str(e)}\nDocument: {get_link_to_form(doc.doctype, doc.name)}"
			)


def trigger_value_change_notifications(doc, method=None):
	"""
	Trigger WhatsApp notifications when specific field values change
	
	Args:
		doc: The document that was updated
		method: The event method
	"""
	if doc.is_new():
		return
	
	# Get all enabled value change notifications for this doctype
	notifications = frappe.get_all(
		"Whatsapp Notification",
		filters={
			"enabled": 1,
			"document_type": doc.doctype,
			"event": "Value Change",
		},
		fields=["name", "value_changed"]
	)
	
	# Check each notification
	for notif in notifications:
		if not notif.value_changed:
			continue
		
		# Check if the specified field has changed
		if doc.has_value_changed(notif.value_changed):
			try:
				notification = frappe.get_doc("Whatsapp Notification", notif.name)
				notification.send_notification(doc)
			except Exception as e:
				frappe.log_error(
					title=f"WhatsApp Notification Error: {notif.name}",
					message=f"Error sending value change notification: {str(e)}\nDocument: {get_link_to_form(doc.doctype, doc.name)}"
				)
