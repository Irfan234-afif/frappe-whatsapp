# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt or (at your option) any later version

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
import whatsapp.whatsapp as whatsapp_api

class TestGlobalAPI(FrappeTestCase):
    def setUp(self):
        # Create a mock session
        if not frappe.db.exists("Whatsapp Session", "Test_Global_Session"):
            self.session = frappe.get_doc({
                "doctype": "Whatsapp Session",
                "session_name": "Test_Global_Session",
                "status": "Connected"
            }).insert()
        else:
            self.session = frappe.get_doc("Whatsapp Session", "Test_Global_Session")
            self.session.status = "Connected"
            self.session.save()

    def tearDown(self):
        frappe.db.rollback()

    @patch('whatsapp.whatsapp.services.waha.WAHAProvider.send_message')
    def test_send_message_explicit_session(self, mock_send):
        mock_send.return_value = {"status": "sent"}
        
        response = whatsapp_api.send_message(
            to_number="1234567890", 
            message="Hello", 
            session="Test_Global_Session"
        )
        
        mock_send.assert_called_once_with("1234567890", "Hello")
        self.assertEqual(response, {"status": "sent"})

    @patch('whatsapp.whatsapp.services.waha.WAHAProvider.send_message')
    def test_send_message_default_session(self, mock_send):
        mock_send.return_value = {"status": "sent"}
        
        # Ensure we have a connected session (set up in setUp)
        
        response = whatsapp_api.send_message(
            to_number="1234567890", 
            message="Hello Default"
        )
        
        mock_send.assert_called_once_with("1234567890", "Hello Default")
        self.assertEqual(response, {"status": "sent"})

    def test_send_message_no_session_error(self):
        # Temporarily disconnect all sessions
        frappe.db.sql("UPDATE `tabWhatsapp Session` SET status = 'Disconnected'")
        
        with self.assertRaises(frappe.ValidationError):
            whatsapp_api.send_message(
                to_number="1234567890", 
                message="Should fail"
            )
