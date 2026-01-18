import abc

class WhatsappProvider(abc.ABC):
    def __init__(self, session_doc):
        self.session_doc = session_doc

    @abc.abstractmethod
    def start_session(self):
        pass

    @abc.abstractmethod
    def stop_session(self):
        pass

    @abc.abstractmethod
    def get_qr_code(self):
        pass

    @abc.abstractmethod
    def get_status(self):
        pass

    @abc.abstractmethod
    def send_message(self, to_number, message, message_id=None):
        pass
