# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock

class TestWhatsappSession(FrappeTestCase):
    def setUp(self):
        # Create settings
        settings = frappe.get_single("Whatsapp Settings")
        settings.default_provider = "WAHA"
        settings.api_url = "http://test-url"
        settings.api_key = "secret"
        settings.save()

        # Create a test session
        if not frappe.db.exists("Whatsapp Session", "Test Session"):
            self.session = frappe.get_doc({
                "doctype": "Whatsapp Session",
                "session_name": "Test Session"
            }).insert()
        else:
            self.session = frappe.get_doc("Whatsapp Session", "Test Session")

    def tearDown(self):
        # Cleanup
        frappe.db.rollback()

    @patch('whatsapp.whatsapp.services.waha.requests.post')
    def test_start_session_success(self, mock_post):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "Test Session", "status": "STARTING"}
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Call start_session
        response = self.session.start_session()

        # Assertions
        mock_post.assert_called_once()
        self.assertEqual(response.get("status"), "STARTING")
        self.session.reload()
    
    @patch('whatsapp.whatsapp.services.waha.requests.post')
    @patch('whatsapp.whatsapp.services.waha.requests.get')
    def test_start_session_flow(self, mock_get, mock_post):
        # Mock start response
        mock_post_response = MagicMock()
        mock_post_response.json.return_value = {"name": "Test Session", "status": "STARTING"}
        mock_post.return_value = mock_post_response

        # Mock status response (called after start)
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = [{"name": "Test Session", "status": "CheckStatus"}]
        mock_get.return_value = mock_get_response

        self.session.start_session()
        self.session.reload()
        self.assertEqual(self.session.status, "CheckStatus")

    @patch('whatsapp.whatsapp.services.waha.requests.post')
    @patch('whatsapp.whatsapp.services.waha.requests.get')
    def test_stop_session_flow(self, mock_get, mock_post):
        # Mock stop response
        mock_post.return_value.json.return_value = {"success": True}
        
        # Mock status response (called after stop)
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = [] # Session list empty implies stopped
        
        self.session.stop_session()
        self.session.reload()
        self.assertEqual(self.session.status, "STOPPED")

    @patch('whatsapp.whatsapp.services.waha.requests.get')
    def test_scan_qr_success(self, mock_get):
        # Mock QR code response (image content)
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"fake_image_data"

        qr_html = self.session.scan_qr()
        
        self.assertIn("data:image/png;base64", qr_html)
        self.session.reload()
        self.assertIn("data:image/png;base64", self.session.qr_code_image)
