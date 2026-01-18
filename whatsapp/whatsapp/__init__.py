import frappe

__version__ = "0.0.1"

def send_message(to_number, message, session=None):
    """
    Send a WhatsApp message.
    
    Args:
        to_number (str): The recipient's phone number.
        message (str): The text message to send.
        session (str, optional): The name of the Whatsapp Session to use. 
                                 If None, uses the first "Connected" session.
    
    Returns:
        dict: The response from the provider sending the message.
    """
    if session:
        session_doc = frappe.get_doc("Whatsapp Session", session)
    else:
        # Find the first connected session
        filters = {"status": "Connected"}
        sessions = frappe.get_all("Whatsapp Session", filters=filters, limit=1)
        
        if not sessions:
            frappe.throw("No connected WhatsApp session found. Please start a session or specify one explicitly.")
            
        session_doc = frappe.get_doc("Whatsapp Session", sessions[0].name)
        
    return session_doc.get_provider_instance().send_message(to_number, message)
