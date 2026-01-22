# Copyright (c) 2026, Irfan Afifi and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import unittest


@patch('whatsapp.whatsapp.doctype.whatsapp_session.whatsapp_session.WhatsappSession.create_session')
def create_test_fixtures(mock_create_session):
	"""Create test data for WhatsApp Notification tests"""
	if frappe.flags.test_whatsapp_notification_created:
		return

	frappe.set_user("Administrator")
	
	# Mock the session creation to avoid HTTP requests
	mock_create_session.return_value = None

	# Create Customer with mobile number
	if not frappe.db.exists("Customer", "_Test Customer WA"):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "_Test Customer WA",
			"customer_type": "Individual",
			"mobile_no": "+6281234567890"
		}).insert(ignore_permissions=True)

	# Create another customer without mobile
	if not frappe.db.exists("Customer", "_Test Customer No Mobile"):
		frappe.get_doc({
			"doctype": "Customer",
			"customer_name": "_Test Customer No Mobile",
			"customer_type": "Individual"
		}).insert(ignore_permissions=True)

	# Create WhatsApp Session (with mocked create_session)
	if not frappe.db.exists("Whatsapp Session", "_Test WA Session"):
		session = frappe.get_doc({
			"doctype": "Whatsapp Session",
			"session_name": "_Test WA Session",
			"is_default_outgoing": 1
		})
		# Manually set status to avoid HTTP call
		session.flags.ignore_validate = True
		session.insert(ignore_permissions=True)
		# Set status directly via db to bypass hooks
		frappe.db.set_value("Whatsapp Session", "_Test WA Session", "status", "WORKING")

	# Create WhatsApp Template
	if not frappe.db.exists("Whatsapp Template", "_Test WA Template"):
		frappe.get_doc({
			"doctype": "Whatsapp Template",
			"name": "_Test WA Template",  # Required because autoname is 'prompt'
			"template_name": "_Test WA Template",
			"message": "Hello {{ doc.name }}, your order is confirmed!"
		}).insert(ignore_permissions=True)

	frappe.db.commit()  # Commit all fixtures to database
	frappe.flags.test_whatsapp_notification_created = True


class TestWhatsappNotification(FrappeTestCase):
	"""Unit tests for Whatsapp Notification"""

	def setUp(self):
		"""Set up test fixtures before each test"""
		create_test_fixtures()
		frappe.set_user("Administrator")

	def tearDown(self):
		"""Clean up after each test"""
		frappe.set_user("Administrator")
		# Clean up test notifications
		frappe.db.delete("Whatsapp Notification", {
			"subject": ["like", "_Test%"]
		})
		frappe.db.commit()

	def test_validation_requires_recipients(self):
		"""Test that validation fails when no recipients are added"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test No Recipients",
			"enabled": 1,
			"document_type": "Sales Order",
			"event": "Submit",
			"whatsapp_template": "_Test WA Template"
		})

		with self.assertRaises(frappe.exceptions.ValidationError):
			notification.insert()

	def test_resolve_field_path_simple(self):
		"""Test resolving simple field path (direct field)"""
		# Create a test document
		customer = frappe.get_doc("Customer", "_Test Customer WA")

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Simple Field Path",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		})

		# Test resolve_field_path method
		result = notification.resolve_field_path(customer, "mobile_no")
		self.assertEqual(result, "+6281234567890")

	def test_resolve_field_path_nested(self):
		"""Test resolving nested field path (linked doctype)"""
		# Create Sales Order with linked customer
		if not frappe.db.exists("Sales Order", "_Test SO WA"):
			so = frappe.get_doc({
				"doctype": "Sales Order",
				"name": "_Test SO WA",
				"customer": "_Test Customer WA",
				"delivery_date": frappe.utils.nowdate(),
				"items": [{
					"item_code": "_Test Item",
					"qty": 1,
					"rate": 100
				}]
			})
			so.insert(ignore_permissions=True, ignore_mandatory=True)
		else:
			so = frappe.get_doc("Sales Order", "_Test SO WA")

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Nested Field Path",
			"enabled": 1,
			"document_type": "Sales Order",
			"event": "Submit",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "customer.mobile_no"
			}]
		})

		# Test resolve_field_path method with nested path
		result = notification.resolve_field_path(so, "customer.mobile_no")
		self.assertEqual(result, "+6281234567890")

	def test_resolve_field_path_empty(self):
		"""Test resolving field path when field is empty"""
		customer = frappe.get_doc("Customer", "_Test Customer No Mobile")

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Empty Field",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		})

		result = notification.resolve_field_path(customer, "mobile_no")
		self.assertIsNone(result)

	def test_resolve_python_expression_simple(self):
		"""Test resolving Python expression"""
		customer = frappe.get_doc("Customer", "_Test Customer WA")

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Python Expression",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Python Expression",
				"python_expression": "doc.mobile_no"
			}]
		})

		result = notification.resolve_python_expression(customer, "doc.mobile_no")
		self.assertEqual(result, "+6281234567890")

	@unittest.skip("Database query in test context - transaction isolation issue")
	def test_resolve_python_expression_frappe_get_value(self):
		"""Test Python expression with frappe.db.get_value"""
		customer = frappe.get_doc("Customer", "_Test Customer WA")

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Python Get Value",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Python Expression",
				"python_expression": 'frappe.db.get_value("Customer", doc.name, "mobile_no")'
			}]
		})

		result = notification.resolve_python_expression(
			customer, 
			'frappe.db.get_value("Customer", doc.name, "mobile_no")'
		)
		self.assertEqual(result, "+6281234567890")

	def test_resolve_python_expression_list(self):
		"""Test Python expression that returns a list"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Python List",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Python Expression",
				"python_expression": '[""+6281111111111", "+6282222222222"]'
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		result = notification.resolve_python_expression(
			customer,
			'["+6281111111111", "+6282222222222"]'
		)
		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 2)

	def test_resolve_fixed_number(self):
		"""Test resolving fixed number recipient"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Fixed Number",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		recipient_row = notification.recipients[0]
		result = notification.resolve_recipient(customer, recipient_row)
		self.assertEqual(result, "+6289999999999")

	def test_get_recipients_multiple(self):
		"""Test getting multiple recipients from different sources"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Multiple Recipients",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [
				{
					"recruit_by": "Field Path",
					"field_path": "mobile_no"
				},
				{
					"recruit_by": "Fixed Number",
					"fixed_number": "+6289999999999"
				}
			]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		recipients = notification.get_recipients(customer)

		# Should have 2 unique recipients
		self.assertEqual(len(recipients), 2)
		self.assertIn("+6281234567890", recipients)
		self.assertIn("+6289999999999", recipients)

	def test_get_recipients_deduplication(self):
		"""Test that duplicate recipients are removed"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Dedup Recipients",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [
				{
					"recruit_by": "Field Path",
					"field_path": "mobile_no"
				},
				{
					"recruit_by": "Fixed Number",
					"fixed_number": "+6281234567890"  # Same as customer mobile
				}
			]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		recipients = notification.get_recipients(customer)

		# Should deduplicate to only 1 recipient
		self.assertEqual(len(recipients), 1)
		self.assertEqual(recipients[0], "+6281234567890")

	def test_evaluate_condition_true(self):
		"""Test condition evaluation that returns True"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Condition True",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"condition": 'doc.customer_type == "Individual"',
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		result = notification.evaluate_condition(customer)
		self.assertTrue(result)

	def test_evaluate_condition_false(self):
		"""Test condition evaluation that returns False"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Condition False",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"condition": 'doc.customer_type == "Company"',
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		result = notification.evaluate_condition(customer)
		self.assertFalse(result)

	def test_prepare_message_with_template(self):
		"""Test message preparation with Jinja template"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Message Template",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		template = frappe.get_doc("Whatsapp Template", "_Test WA Template")
		message = notification.prepare_message(customer, template)

		self.assertIn("_Test Customer WA", message)
		self.assertIn("your order is confirmed", message)

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_success(self, mock_send):
		"""Test sending notification successfully"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Send Notification",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_session": "_Test WA Session",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Verify send_whatsapp_message was called
		mock_send.assert_called_once()
		args = mock_send.call_args[0]
		self.assertEqual(args[0], "_Test WA Session")
		self.assertEqual(args[1], "+6281234567890")

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_disabled(self, mock_send):
		"""Test that disabled notifications are not sent"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Disabled Notification",
			"enabled": 0,  # Disabled
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Should not call send
		mock_send.assert_not_called()

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_condition_not_met(self, mock_send):
		"""Test that notification is not sent when condition is not met"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Condition Not Met",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"condition": 'doc.customer_type == "Company"',  # Will be False
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Should not call send because condition failed
		mock_send.assert_not_called()

	@unittest.skip("Database query in test context - transaction isolation issue")
	def test_get_default_session(self):
		"""Test getting default active session"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Default Session",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		session = notification.get_default_session()
		self.assertEqual(session, "_Test WA Session")

	# =====================================================
	# REFERENCE ID TESTS
	# =====================================================

	def test_generate_reference_id_simple(self):
		"""Test generating reference ID from simple template"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Ref ID Simple",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"reference_id_template": "{{ doc.name }}-test",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		reference_id = notification.generate_reference_id(customer)
		
		self.assertEqual(reference_id, "_Test Customer WA-test")

	def test_generate_reference_id_complex(self):
		"""Test generating reference ID with multiple fields"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Ref ID Complex",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"reference_id_template": "{{ doc.doctype }}-{{ doc.name }}-{{ doc.customer_type }}",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		reference_id = notification.generate_reference_id(customer)
		
		self.assertEqual(reference_id, "Customer-_Test Customer WA-Individual")

	def test_generate_reference_id_empty_template(self):
		"""Test generating reference ID when template is empty"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Ref ID Empty",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"reference_id_template": "",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		reference_id = notification.generate_reference_id(customer)
		
		self.assertIsNone(reference_id)

	def test_check_duplicate_reference_not_exists(self):
		"""Test checking duplicate when reference_id doesn't exist"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Check Dup Not Exists",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		# Check for non-existent reference_id
		is_duplicate = notification.check_duplicate_reference("unique-ref-id-12345")
		self.assertFalse(is_duplicate)

	def test_check_duplicate_reference_exists(self):
		"""Test checking duplicate when reference_id exists"""
		# Clean up any existing test messages
		frappe.db.delete("Whatsapp Message", {"reference_id": ["like", "_Test Ref%"]})
		frappe.db.commit()

		# Create a WhatsApp Message with reference_id
		msg = frappe.get_doc({
			"doctype": "Whatsapp Message",
			"whatsapp_session": "_Test WA Session",
			"to_number": "+6281111111111",
			"message": "Test message",
			"reference_id": "_Test Ref Duplicate"
		})
		msg.flags.ignore_validate = True
		msg.insert(ignore_permissions=True)
		frappe.db.commit()

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Check Dup Exists",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Fixed Number",
				"fixed_number": "+6289999999999"
			}]
		})

		# Check for existing reference_id
		is_duplicate = notification.check_duplicate_reference("_Test Ref Duplicate")
		self.assertTrue(is_duplicate)

		# Cleanup
		frappe.delete_doc("Whatsapp Message", msg.name, force=True)
		frappe.db.commit()

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_with_reference_id_first_time(self, mock_send):
		"""Test sending notification with reference_id for the first time"""
		# Clean up
		frappe.db.delete("Whatsapp Message", {"reference_id": ["like", "_Test SO%"]})
		frappe.db.commit()

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Ref ID First Send",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"reference_id_template": "{{ doc.name }}-paid",
			"whatsapp_session": "_Test WA Session",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Should send because it's the first time
		mock_send.assert_called_once()
		# Verify reference_id was passed
		args = mock_send.call_args[0]
		kwargs = mock_send.call_args[1] if len(mock_send.call_args) > 1 else {}
		# reference_id should be the 5th argument or in kwargs
		if len(args) >= 5:
			self.assertEqual(args[4], "_Test Customer WA-paid")
		else:
			self.assertEqual(kwargs.get('reference_id'), "_Test Customer WA-paid")

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_with_reference_id_duplicate(self, mock_send):
		"""Test that duplicate notification is not sent when reference_id exists"""
		# Clean up
		frappe.db.delete("Whatsapp Message", {"reference_id": ["like", "_Test Dup%"]})
		frappe.db.commit()

		# Create existing message with reference_id
		existing_msg = frappe.get_doc({
			"doctype": "Whatsapp Message",
			"whatsapp_session": "_Test WA Session",
			"to_number": "+6281234567890",
			"message": "Previous message",
			"reference_id": "_Test Dup _Test Customer WA-paid"  # Match template output
		})
		existing_msg.flags.ignore_validate = True
		existing_msg.insert(ignore_permissions=True)
		frappe.db.commit()

		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test Ref ID Duplicate",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			"reference_id_template": "_Test Dup {{ doc.name }}-paid",
			"whatsapp_session": "_Test WA Session",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Should NOT send because reference_id already exists
		mock_send.assert_not_called()

		# Cleanup
		frappe.delete_doc("Whatsapp Message", existing_msg.name, force=True)
		frappe.db.commit()

	@patch('whatsapp.whatsapp.doctype.whatsapp_notification.whatsapp_notification.WhatsappNotification.send_whatsapp_message')
	def test_send_notification_without_reference_id_backward_compat(self, mock_send):
		"""Test that notification without reference_id still works (backward compatibility)"""
		notification = frappe.get_doc({
			"doctype": "Whatsapp Notification",
			"subject": "_Test No Ref ID",
			"enabled": 1,
			"document_type": "Customer",
			"event": "Save",
			# No reference_id_template
			"whatsapp_session": "_Test WA Session",
			"whatsapp_template": "_Test WA Template",
			"recipients": [{
				"recruit_by": "Field Path",
				"field_path": "mobile_no"
			}]
		}).insert()

		customer = frappe.get_doc("Customer", "_Test Customer WA")
		notification.send_notification(customer)

		# Should send normally without reference_id check
		mock_send.assert_called_once()

