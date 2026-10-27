import hashlib
import hmac
import json
import time

from odoo import http
from odoo.http import request


class ViesacWebhookController(http.Controller):
    @staticmethod
    def _valid_signature(secret, timestamp, signature, raw_body):
        if not secret or not timestamp or not signature:
            return False
        try:
            if not timestamp.isascii() or not timestamp.isdecimal() or abs(time.time() - int(timestamp)) > 300:
                return False
        except (TypeError, ValueError):
            return False
        signed = timestamp.encode('ascii') + b'.' + raw_body
        expected = 'sha256=' + hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)

    @http.route('/viesac/webhook', type='http', auth='public', methods=['POST'], csrf=False)
    def viesac_webhook(self, **kwargs):
        secret = request.env['ir.config_parameter'].sudo().get_param('viesac.webhook_secret', '')
        headers = request.httprequest.headers
        raw_body = request.httprequest.get_data()
        if not self._valid_signature(secret, headers.get('X-Viesac-Timestamp'),
                                     headers.get('X-Viesac-Signature'), raw_body):
            return request.make_json_response({'error': 'Invalid webhook signature'}, status=401)
        try:
            payload = json.loads(raw_body)
            data = payload.get('data')
            reference = data.get('reference_number') if isinstance(data, dict) else None
        except (ValueError, AttributeError):
            return request.make_json_response({'error': 'Invalid JSON'}, status=400)
        if not isinstance(reference, str) or not reference:
            return request.make_json_response({'error': 'Missing audit reference'}, status=400)
        audits = request.env['viesac.audit.log'].sudo().search([('name', '=', reference)])
        if not audits:
            return request.make_json_response({'status': 'not_found'})
        # Refetch current API state to tolerate delayed, duplicate and out-of-order events.
        for audit in audits:
            audit.action_refresh_status()
        return request.make_json_response({'status': 'processed', 'reference': reference})
