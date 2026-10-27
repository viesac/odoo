# -*- coding: utf-8 -*-
from unittest.mock import patch, Mock
from types import SimpleNamespace
import hashlib
import hmac
import time
from odoo.tests import tagged
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import common
from odoo.exceptions import UserError, AccessError
from ..controllers.webhook import ViesacWebhookController
from ..models.res_config_settings import AVAILABLE_LOCALES
from ..models.viesac_api_client import ViesacApiClient


@tagged('post_install', '-at_install')
class TestViesacVatCompliance(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.simple_accountman = common.new_test_user(
            cls.env, login='viesac_account_user',
            groups='account.group_account_user',
            company_id=cls.env.company.id,
            company_ids=[(6, 0, cls.env.user.company_ids.ids)],
        )

    def setUp(self):
        super().setUp()
        self.param_obj = self.env['ir.config_parameter'].sudo()
        self.param_obj.set_param('viesac.base_url', 'https://viesac.eu')
        self.param_obj.set_param('viesac.api_key', 'test_viesac_api_key')
        self.param_obj.set_param('viesac.auto_attach_certificates', 'True')

    def test_01_offline_format_validation(self):
        """Verify thin client offline format check without API key."""
        self.param_obj.set_param('viesac.api_key', '')
        partner = self.env['res.partner'].create({
            'name': 'Offline Format Test Partner',
            'vat': 'DE123456788',
            'country_id': self.env.ref('base.de').id,
        })
        res = partner.action_verify_vat()
        self.assertEqual(partner.viesac_vat_status, 'unverified')
        self.assertEqual(partner.viesac_official_source, 'FORMAT_CHECK_ONLY')
        self.assertEqual(res.get('tag'), 'display_notification')

    def test_02_online_vat_eori_verification(self):
        """Verify partner verification with mocked VIESAC API audit & certificate download."""
        partner = self.env['res.partner'].create({
            'name': 'BMW Test Partner',
            'vat': 'DE129273398',
            'viesac_eori_number': 'DE129273398000',
            'country_id': self.env.ref('base.de').id,
            'is_company': True,
        })

        mock_validate = {
            'status': 'valid',
            'source': 'VALID (BZSt)',
            'company_name': 'BAYERISCHE MOTOREN WERKE AG',
        }
        mock_audit = {
            'reference_number': 'AUD-2026-TEST-1',
            'status': 'valid',
            'vat_status': 'valid',
            'official_source': 'Bundeszentralamt für Steuern (BZSt / VIES)',
            'consultation_number': 'WFRV-TEST-112233',
            'verification_code': 'VALID (BZSt)',
        }
        mock_pdf = {'success': True, 'content': b'%PDF-test', 'content_type': 'application/pdf'}
        mock_xml = {'success': True, 'content': b'<xml>test</xml>', 'content_type': 'application/xml'}

        with patch.object(ViesacApiClient, 'validate_vat', return_value=mock_validate):
            partner.action_verify_vat()
            self.assertEqual(partner.viesac_vat_status, 'valid')
            self.assertEqual(partner.viesac_official_source, 'VALID (BZSt)')

        with patch.object(ViesacApiClient, 'create_audit', return_value=mock_audit):
            with patch.object(ViesacApiClient, 'download_certificate', side_effect=[mock_pdf, mock_xml]):
                partner.action_verify_hybrid()
                self.assertEqual(partner.viesac_consultation_number, 'WFRV-TEST-112233')
                self.assertEqual(partner.viesac_audit_count, 1)

    def test_03_vendor_bill_strict_defense(self):
        """Verify AP strict policy blocks vendor bill posting for invalid VAT."""
        self.param_obj.set_param('viesac.vendor_bill_mode', 'strict')
        vendor = self.env['res.partner'].create({
            'name': 'Bogus Supplier Ltd',
            'vat': 'GB000000000',
            'viesac_vat_status': 'invalid',
            'country_id': self.env.ref('base.uk').id,
        })
        product = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': vendor.id,
            'invoice_date': '2026-10-27',
            'journal_id': self.company_data['default_journal_purchase'].id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_a.id,
                'account_id': self.company_data['default_account_expense'].id,
                'quantity': 1,
                'price_unit': 500.0,
            })],
        })

        mock_invalid_audit = {
            'reference_number': 'AUD-INV-1',
            'status': 'invalid',
            'vat_status': 'invalid',
        }
        with patch.object(ViesacApiClient, 'create_audit', return_value=mock_invalid_audit):
            with self.assertRaises(UserError):
                bill.action_post()

    def _partner(self, **values):
        return self.env['res.partner'].create(dict(name='Review Partner', vat='DE129273398',
            country_id=self.env.ref('base.de').id, **values))

    def _audit(self, partner, **values):
        return self.env['viesac.audit.log'].create(dict(name='VAC-REVIEW-1', partner_id=partner.id,
            country_code='DE', vat_number='129273398', **values))

    def test_format_scope_never_becomes_registry_valid(self):
        partner = self._partner()
        with patch.object(ViesacApiClient, 'validate_vat', return_value={
                'status': 'valid', 'registry_checked': False, 'registration_valid': None}):
            partner.action_verify_vat()
        self.assertEqual(partner.viesac_vat_status, 'unverified')

    def test_edit_identifier_resets_result(self):
        partner = self._partner(viesac_vat_status='valid', viesac_consultation_number='OLD',
            viesac_last_reference='OLD', viesac_eori_same_as_vat=True, viesac_eori_status='valid')
        partner.vat = 'FR40303265045'
        self.assertEqual(partner.viesac_vat_status, 'unverified')
        self.assertFalse(partner.viesac_consultation_number)
        self.assertFalse(partner.viesac_last_reference)
        self.assertEqual(partner.viesac_eori_number, partner.vat)
        self.assertEqual(partner.viesac_eori_status, 'unverified')

    def test_old_audit_does_not_overwrite_new_tax_id(self):
        partner = self._partner(viesac_last_reference='VAC-REVIEW-1')
        audit = self._audit(partner)
        partner.vat = 'FR40303265045'
        self.param_obj.set_param('viesac.auto_attach_certificates', 'False')
        with patch.object(ViesacApiClient, 'get_audit', return_value={'status': 'valid', 'vat_status': 'valid'}):
            audit.action_refresh_status()
        self.assertEqual(partner.viesac_vat_status, 'unverified')

    def test_polling_releases_delivery_hold(self):
        partner = self._partner()
        order = self.env['sale.order'].create({'partner_id': partner.id, 'viesac_delivery_held': True})
        audit = self._audit(partner, sale_order_id=order.id)
        self.param_obj.set_param('viesac.auto_attach_certificates', 'False')
        with patch.object(ViesacApiClient, 'get_audit', return_value={'status': 'valid', 'vat_status': 'valid'}):
            audit.action_refresh_status()
        self.assertFalse(order.viesac_delivery_held)

    def test_delivery_hold_blocks_stock_completion(self):
        partner = self._partner()
        order = self.env['sale.order'].create({'partner_id': partner.id, 'viesac_delivery_held': True})
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1)
        picking = self.env['stock.picking'].create({'partner_id': partner.id, 'sale_id': order.id,
            'picking_type_id': warehouse.out_type_id.id,
            'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id})
        with self.assertRaises(UserError):
            picking._action_done()

    def test_company_rule_blocks_cross_company_audit(self):
        partner = self._partner()
        other = self._audit(partner, company_id=self.company_data_2['company'].id)
        model = self.env['viesac.audit.log'].with_user(self.simple_accountman).with_context(
            allowed_company_ids=[self.env.company.id])
        self.assertFalse(model.search([('id', '=', other.id)]))
        with self.assertRaises(AccessError):
            model.browse(other.id).action_refresh_status()

    def test_api_key_hidden_from_non_admin_settings(self):
        fields = self.env['res.config.settings'].with_user(self.simple_accountman).fields_get()
        self.assertNotIn('viesac_api_key', fields)
        self.assertNotIn('viesac_webhook_secret', fields)

    def test_repeated_document_audit_uses_stable_key(self):
        partner = self._partner()
        order = self.env['sale.order'].create({'partner_id': partner.id})
        self.param_obj.set_param('viesac.auto_attach_certificates', 'False')
        result = {'reference_number': 'VAC-IDEMPOTENT', 'status': 'valid', 'vat_status': 'valid'}
        with patch.object(ViesacApiClient, 'create_audit', return_value=result) as client:
            first = self.env['viesac.audit.log'].create_or_run_audit(partner, order=order)
            second = self.env['viesac.audit.log'].create_or_run_audit(partner, order=order)
        self.assertEqual(first, second)
        self.assertEqual(client.call_args_list[0].kwargs['idempotency_key'],
                         client.call_args_list[1].kwargs['idempotency_key'])

    def test_http_errors_are_not_audit_success(self):
        response = Mock(status_code=422, content=b'{"message":"Invalid VAT"}')
        response.json.return_value = {'message': 'Invalid VAT', 'errors': {'vat_number': ['required']}}
        with patch('requests.post', return_value=response):
            result = ViesacApiClient.create_audit('fake-key', {'type': 'vat'})
        self.assertIn('error', result)
        self.assertEqual(result['http_status'], 422)

    def test_malformed_json_is_not_success(self):
        response = Mock(status_code=200, content=b'<html>Proxy</html>')
        response.json.side_effect = ValueError('not JSON')
        self.assertIn('error', ViesacApiClient._json_response(response))

    def test_timestamped_webhook_signatures(self):
        raw = b'{"data":{"reference_number":"VAC-1"}}'
        ts = str(int(time.time()))
        sig = 'sha256=' + hmac.new(b'secret', ts.encode()+b'.'+raw, hashlib.sha256).hexdigest()
        verify = ViesacWebhookController._valid_signature
        self.assertTrue(verify('secret', ts, sig, raw))
        self.assertFalse(verify('', ts, sig, raw))
        self.assertFalse(verify('wrong', ts, sig, raw))
        self.assertFalse(verify('secret', ts, sig, raw+b' '))
        old = str(int(ts)-600)
        old_sig = 'sha256=' + hmac.new(b'secret', old.encode()+b'.'+raw, hashlib.sha256).hexdigest()
        self.assertFalse(verify('secret', old, old_sig, raw))

    def test_certificate_locale_codes_match_api(self):
        self.assertEqual(len(AVAILABLE_LOCALES), 23)
        codes = dict(AVAILABLE_LOCALES)
        self.assertIn('cz', codes)
        self.assertIn('gr', codes)
        self.assertNotIn('cs', codes)
        self.assertNotIn('el', codes)

    def test_certificate_attachments_are_idempotent_and_archived(self):
        partner = self._partner()
        audit = self._audit(partner, status='valid', vat_status='valid')
        data = {'success': True, 'content': b'%PDF-test'}
        with patch.object(ViesacApiClient, 'download_certificate', return_value=data):
            audit._download_and_attach_certificates()
            audit._download_and_attach_certificates()
        attachments = self.env['ir.attachment'].search([('res_model', '=', 'viesac.audit.log'), ('res_id', '=', audit.id)])
        self.assertEqual(len(attachments), 2)
        self.assertIn(audit.pdf_attachment_id, attachments)

    def test_tax_review_does_not_archive_or_replace_taxes(self):
        original = self.company_data['default_tax_sale']
        wizard = self.env['viesac.tax.sync.wizard'].create({'action_type': 'safe_rollover'})
        before = self.env['account.tax'].search_count([])
        wizard._execute_safe_rollover()
        self.assertTrue(original.active)
        self.assertEqual(before, self.env['account.tax'].search_count([]))
        before_fp = self.env['account.fiscal.position'].search_count([])
        wizard._configure_eu_oss()
        self.assertEqual(before_fp, self.env['account.fiscal.position'].search_count([]))

    def test_invoice_evidence_does_not_follow_partner_status(self):
        partner = self._partner(viesac_vat_status='valid')
        move = self.env['account.move'].create({'move_type': 'out_invoice', 'partner_id': partner.id,
            'journal_id': self.company_data['default_journal_sale'].id})
        self._audit(partner, move_id=move.id, vat_status='invalid')
        self.assertEqual(move.viesac_vat_status, 'invalid')
        partner.viesac_vat_status = 'pending'
        self.assertEqual(move.viesac_vat_status, 'invalid')

    def test_iso_catalog_timestamp(self):
        parsed = self.env['viesac.vat.rate']._parse_verified_at('2026-10-27T12:00:00+02:00')
        self.assertEqual(str(parsed), '2026-10-27 10:00:00')
        self.assertFalse(self.env['viesac.vat.rate']._parse_verified_at(None))

    def test_chatter_renders_html_and_escapes_external_values(self):
        partner = self._partner()
        audit = self._audit(partner, status='valid', official_source='<img src=x onerror=alert(1)>')
        audit._post_chatter_notification([partner])
        message = partner.message_ids.sorted('id', reverse=True)[:1]
        self.assertIn('<strong>VIESAC verification</strong>', message.body)
        self.assertNotIn('&lt;strong&gt;', message.body)
        self.assertNotIn('<img ', message.body)
        self.assertIn('&lt;img', message.body)
