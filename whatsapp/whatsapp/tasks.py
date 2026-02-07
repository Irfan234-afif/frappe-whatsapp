# Copyright (c) 2026, Irfan Afifi and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import get_link_to_form

frappe.utils.logger.set_log_level("DEBUG")
logger = frappe.logger("whatsapp", allow_site=True, file_count=3)

def process_scheduled_notifications():
    """
    Process all scheduled WhatsApp notifications.
    This function is called by the scheduler every few minutes.
    
    It finds all enabled scheduled notifications and evaluates their conditions
    against matching documents to determine if notifications should be sent.
    """
    # Get all enabled scheduled notifications
    notifications = frappe.get_all(
        "Whatsapp Notification",
        filters={
            "enabled": 1,
            "event": "Scheduled",
        },
        pluck="name"
    )
    
    logger.info(f"[WhatsApp Scheduler] Found {len(notifications)} scheduled notifications to process")
    
    for notification_name in notifications:
        try:
            process_single_scheduled_notification(notification_name)
        except Exception as e:
            frappe.log_error(
                title=f"Scheduled WhatsApp Notification Error: {notification_name}",
                message=str(e)
            )


def process_single_scheduled_notification(notification_name: str):
    """
    Process a single scheduled notification.
    
    Args:
        notification_name: Name of the Whatsapp Notification document
    """
    notification = frappe.get_doc("Whatsapp Notification", notification_name)
    
    if not notification.document_type:
        return
    
    # If no scheduled_filters, skip to prevent processing all documents
    if not notification.scheduled_filters:
        logger.warning(
            f"[WhatsApp Scheduler] Skipping {notification_name}: No initial filters defined. "
            "Please add scheduled_filters to limit the documents to process."
        )
        return
    
    # Parse scheduled_filters
    try:
        filters = json.loads(notification.scheduled_filters)
        if not isinstance(filters, dict):
            raise ValueError("scheduled_filters must be a JSON object")
    except (json.JSONDecodeError, ValueError) as e:
        frappe.log_error(
            title=f"WhatsApp Notification Filter Parse Error: {notification_name}",
            message=f"Invalid JSON in scheduled_filters: {str(e)}"
        )
        return
    
    # Get documents matching the filters
    docs = frappe.get_all(
        notification.document_type,
        filters=filters,
        pluck="name",
        limit=500
    )
    
    logger.info(
        f"[WhatsApp Scheduler] Processing {len(docs)} documents for notification: {notification_name}"
    )
    
    for doc_name in docs:
        try:
            doc = frappe.get_doc(notification.document_type, doc_name)
            
            # send_notification will:
            # 1. Check the condition
            # 2. Check for duplicate reference_id
            # 3. Send the notification if all checks pass
            notification.send_notification(doc)
            
        except Exception as e:
            frappe.log_error(
                title=f"Scheduled WhatsApp Notification Error: {notification_name}",
                message=f"Error processing {notification.document_type} {doc_name}: {str(e)}"
            )
    
    frappe.db.commit()
