import frappe
from frappe.model.document import Document
from bpo_coach.security import internal_write, is_admin, process_allowed

IMMUTABLE = {'AI Scenario Version', 'AI Action', 'AI Operation'}
SERVER_RECORDS = {'AI Scenario', 'AI Scenario Version', 'AI Asset', 'BPO Training Assignment', 'AI Attempt', 'AI Action', 'AI Dialogue', 'AI Operation', 'BPO Import Record', 'BPO Reminder'}

class BPORecord(Document):
    def validate(self):
        if self.doctype in SERVER_RECORDS and not internal_write():
            frappe.throw('Use the AI Coach application to change this record.', frappe.PermissionError)
        if self.doctype in IMMUTABLE and not self.is_new():
            frappe.throw('Published versions and execution evidence are immutable.')
        if self.doctype in {'BPO Client', 'BPO Process', 'BPO Process Access', 'AI Provider Settings'} and not is_admin():
            frappe.throw('Administrator access required.', frappe.PermissionError)
        if self.doctype == 'BPO Process Access':
            self.access_key = self.member + '|' + self.process
        if self.doctype == 'AI Provider Settings':
            self.text_model = self.text_model or 'openai/gpt-oss-120b'
            self.stt_model = self.stt_model or 'whisper-large-v3-turbo'
            self.tts_model = self.tts_model or 'canopylabs/orpheus-v1-english'
            self.tts_voice = self.tts_voice or 'troy'

    def on_trash(self):
        if self.doctype in SERVER_RECORDS:
            frappe.throw('Training records and evidence cannot be deleted.')
