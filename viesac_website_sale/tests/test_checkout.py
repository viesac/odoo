from types import SimpleNamespace
from unittest.mock import patch

from odoo.tests import TransactionCase, tagged
from ..controllers.main import ViesacWebsiteSaleController
from odoo.addons.viesac_vat_compliance.models.viesac_api_client import ViesacApiClient


@tagged('post_install', '-at_install')
class TestCheckoutVat(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env['ir.config_parameter'].sudo().set_param('viesac.api_key', 'fake-key')
        self.order = SimpleNamespace(state='draft', order_line=[True], fiscal_position_id=42)
        self.request = SimpleNamespace(env=self.env, session={},
            website=SimpleNamespace(sale_get_order=lambda: self.order))
        self.controller = ViesacWebsiteSaleController()

    def test_ajax_check_does_not_change_tax_or_disclose_name(self):
        with patch('odoo.addons.viesac_website_sale.controllers.main.request', self.request), patch.object(
                ViesacApiClient, 'validate_vat', return_value={'status': 'valid', 'company_name': 'Private Name'}):
            result = self.controller.validate_checkout_vat(vat='DE129273398', country_id='999999')
        self.assertTrue(result['valid'])
        self.assertNotIn('company_name', result)
        self.assertEqual(self.order.fiscal_position_id, 42)

    def test_no_cart_does_not_consume_api_quota(self):
        self.request.website.sale_get_order = lambda: None
        with patch('odoo.addons.viesac_website_sale.controllers.main.request', self.request), patch.object(
                ViesacApiClient, 'validate_vat') as api:
            result = self.controller.validate_checkout_vat(vat='DE129273398')
        self.assertEqual(result['status'], 'unavailable')
        api.assert_not_called()

    def test_offline_format_is_not_registry_confirmation(self):
        self.env['ir.config_parameter'].sudo().set_param('viesac.api_key', '')
        with patch('odoo.addons.viesac_website_sale.controllers.main.request', self.request):
            result = self.controller.validate_checkout_vat(vat='DE129273398')
        self.assertFalse(result['valid'])
        self.assertTrue(result['format_valid'])
        self.assertEqual(result['status'], 'unverified')

    def test_session_cache_and_rate_limit(self):
        with patch('odoo.addons.viesac_website_sale.controllers.main.request', self.request), patch.object(
                ViesacApiClient, 'validate_vat', return_value={'status': 'valid'}) as api:
            self.controller.validate_checkout_vat(vat='DE129273398')
            self.controller.validate_checkout_vat(vat='DE129273398')
            self.assertEqual(api.call_count, 1)
            for number in range(4):
                self.controller.validate_checkout_vat(vat='DE12345678%s' % number)
            result = self.controller.validate_checkout_vat(vat='DE111111111')
        self.assertEqual(result['status'], 'rate_limited')
        self.assertEqual(api.call_count, 5)

    def test_api_error_is_not_cached(self):
        with patch('odoo.addons.viesac_website_sale.controllers.main.request', self.request), patch.object(
                ViesacApiClient, 'validate_vat', side_effect=[{'error': 'Invalid API key'}, {'status': 'valid'}]) as api:
            first = self.controller.validate_checkout_vat(vat='EE100247019')
            second = self.controller.validate_checkout_vat(vat='EE100247019')
        self.assertFalse(first['valid'])
        self.assertTrue(second['valid'])
        self.assertEqual(api.call_count, 2)
