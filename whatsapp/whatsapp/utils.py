import frappe

def get_provider(session_doc):
    from whatsapp.whatsapp.services.waha import WAHAProvider
    
    # Provider selection based on settings
    settings = frappe.get_single("Whatsapp Settings")
    if settings.default_provider == "WAHA":
        return WAHAProvider(session_doc)
    
    return WAHAProvider(session_doc) # Default fallback
