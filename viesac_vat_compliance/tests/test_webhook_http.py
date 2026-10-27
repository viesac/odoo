import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from odoo.http import Response
from odoo.tests import TransactionCase, tagged
from ..controllers.webhook import ViesacWebhookController
from ..models.viesac_api_client import ViesacApiClient


@tagged('post_install', '-at_install')
class TestWebhookHttp(TransactionCase):
    def setUp(self):
        super().setUp()
        self.param_obj = self.env['ir.config_parameter'].sudo()
        self.param_obj.set_param('viesac.webhook_secret', 'review-test-secret')
        self.param_obj.set_param('viesac.api_key', 'fake-key')
        self.param_obj.set_param('viesac.auto_attach_certificates', 'False')
        self.controller = ViesacWebhookController()

    def _call(self, body, timestamp=None, signature=None):
        raw = body.encode('utf-8') if isinstance(body, str) else body
        headers = {'Content-Type': 'application/json'}
        if timestamp is not None:
            headers['X-Viesac-Timestamp'] = timestamp
        if signature is not None:
            headers['X-Viesac-Signature'] = signature
        req = SimpleNamespace(
            env=self.env,
            httprequest=SimpleNamespace(headers=headers, get_data=lambda: raw),
            make_json_response=lambda data, status=200: Response(
                json.dumps(data), status=status, mimetype='application/json'
            ),
        )
        with patch('odoo.addons.viesac_vat_compliance.controllers.webhook.request', req):
            return self.controller.viesac_webhook()

    def _headers_sig(self, body, secret='review-test-secret', age=0):
        raw = body.encode('utf-8') if isinstance(body, str) else body
        ts = str(int(time.time()) - age)
        sig = 'sha256=' + hmac.new(secret.encode(), ts.encode() + b'.' + raw, hashlib.sha256).hexdigest()
        return ts, sig

    def test_unsigned_webhook_rejected_over_http(self):
        response = self._call('{}')
        self.assertEqual(response.status_code, 401)

    def test_disabled_webhook_rejected_over_http(self):
        self.param_obj.set_param('viesac.webhook_secret', '')
        ts, sig = self._headers_sig('{}', secret='review-test-secret')
        response = self._call('{}', timestamp=ts, signature=sig)
        self.assertEqual(response.status_code, 401)

    def test_expired_webhook_rejected_over_http(self):
        ts, sig = self._headers_sig('{}', age=600)
        response = self._call('{}', timestamp=ts, signature=sig)
        self.assertEqual(response.status_code, 401)

    def test_signed_invalid_json_rejected_over_http(self):
        body = '[invalid-json'
        ts, sig = self._headers_sig(body)
        response = self._call(body, timestamp=ts, signature=sig)
        self.assertEqual(response.status_code, 400)

    def test_signed_event_refetches_authoritative_audit(self):
        partner = self.env['res.partner'].create({'name': 'Webhook Review'})
        audit = self.env['viesac.audit.log'].create({'name': 'VAC-HTTP-REVIEW', 'partner_id': partner.id})
        body = json.dumps({'event': 'audit.completed', 'data': {'reference_number': audit.name, 'status': 'valid'}})
        ts, sig = self._headers_sig(body)
        with patch.object(ViesacApiClient, 'get_audit', return_value={'status': 'pending', 'vat_status': 'pending'}) as client:
            response = self._call(body, timestamp=ts, signature=sig)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.data.decode('utf-8'))['status'], 'processed')
        client.assert_called_once()
        audit.invalidate_recordset()
        self.assertEqual(audit.status, 'pending')
