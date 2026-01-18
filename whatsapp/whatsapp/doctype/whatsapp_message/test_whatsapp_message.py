# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock

from whatsapp.whatsapp.services.waha import send_waha_message_job

class TestWhatsappMessage(FrappeTestCase):
    def setUp(self):
        # Create settings
        settings = frappe.get_single("Whatsapp Settings")
        settings.default_provider = "WAHA"
        settings.api_url = "http://test-url"
        settings.api_key = "secret"
        settings.save()

        # Create a test session
        if not frappe.db.exists("Whatsapp Session", "Test Messager Session"):
            with patch('whatsapp.whatsapp.services.waha.requests.post') as mock_post:
                mock_post.return_value.status_code = 201
                mock_post.return_value.json.return_value = {"name": "Test Messager Session"}
                self.session = frappe.get_doc({
                    "doctype": "Whatsapp Session",
                    "session_name": "Test Messager Session"
                }).insert()
        else:
            self.session = frappe.get_doc("Whatsapp Session", "Test Messager Session")

    def tearDown(self):
        frappe.db.rollback()

    @patch('whatsapp.whatsapp.services.waha.frappe.enqueue')
    def test_send_message_queues_job(self, mock_enqueue):
        # Create message
        msg = frappe.get_doc({
            "doctype": "Whatsapp Message",
            "whatsapp_session": self.session.name,
            "to_number": "1234567890",
            "message": "Hello World"
        })
        
        # Submit triggers after_insert -> send_message
        msg.insert()
        msg.reload()

        # Assertions
        mock_enqueue.assert_called_once()
        self.assertEqual(msg.status, "Queued")
        self.assertEqual(msg.message_id, "Queued")

    @patch('whatsapp.whatsapp.services.waha.requests.post')
    def test_job_execution_success(self, mock_post):
        # Mock successful send
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "true_TEST_ID", "ack": 0}
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        # Create a message manually
        msg = frappe.get_doc({
            "doctype": "Whatsapp Message",
            "whatsapp_session": self.session.name,
            "to_number": "1234567890",
            "message": "Hello Job"
        })
        msg.insert()
        
        # Manually run the job
        send_waha_message_job(
            session_name=self.session.name,
            to_number="1234567890",
            message="Hello Job",
            message_id=msg.name
        )
        
        msg.reload()
        self.assertEqual(msg.status, "Sent")
        self.assertEqual(msg.message_id, "true_TEST_ID")

    @patch('whatsapp.whatsapp.services.waha.requests.post')
    def test_job_execution_failure(self, mock_post):
        # Mock failed send
        mock_post.side_effect = Exception("API Error")

        msg = frappe.get_doc({
            "doctype": "Whatsapp Message",
            "whatsapp_session": self.session.name,
            "to_number": "1234567890",
            "message": "Fail Msg"
        })
        msg.insert()
        
        # Manually run the job
        send_waha_message_job(
            session_name=self.session.name,
            to_number="1234567890",
            message="Fail Msg",
            message_id=msg.name
        )

        msg.reload()
        self.assertEqual(msg.status, "Failed")
        self.assertIn("API Error", msg.response)
