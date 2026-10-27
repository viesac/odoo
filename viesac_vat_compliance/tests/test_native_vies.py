from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.base_vat.models.res_partner import ResPartner as NativeVatPartner
from ..hooks import post_init_hook


@tagged('post_install', '-at_install')
class TestNativeViesHandover(TransactionCase):
    def setUp(self):
        super().setUp()
        self.params = self.env['ir.config_parameter'].sudo()
        self.params.set_param('viesac.api_key', 'test_configured_key')
        self.params.set_param('viesac.replace_odoo_vies', 'True')
        self.env['res.company'].sudo().search([]).write({'vat_check_vies': False})

    def _partner(self):
        return self.env['res.partner'].create({
            'name': 'Native VAT Integration Test', 'vat': 'EE100247019',
            'country_id': self.env.ref('base.ee').id, 'is_company': True,
        })

    def test_install_hook_disables_company_online_checks(self):
        other = self.env['res.company'].create({'name': 'Second VAT Company'})
        (self.env.company | other).write({'vat_check_vies': True})
        post_init_hook(self.env)
        post_init_hook(self.env)
        self.assertFalse(self.env['res.company'].sudo().search_count([('vat_check_vies', '=', True)]))

    def test_active_viesac_preserves_local_validation_without_network(self):
        self.env.company.vat_check_vies = True  # Even if someone re-enables it later.
        with patch.object(NativeVatPartner, '_check_vies_iap') as native, patch('requests.sessions.Session.request') as network:
            partner = self._partner()
            partner.check_vat()
            partner._compute_vies_valid()
            self.assertEqual(partner._check_vies_iap(), 'pending')
            self.assertEqual(partner._check_vies_update_iap(), {})
        native.assert_not_called()
        network.assert_not_called()
        self.assertFalse(partner.vies_valid)
        self.assertEqual(partner.viesac_vat_status, 'unverified')

    def test_syntax_error_is_rejected_with_viesac(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['res.partner'].create({'name': 'Typo', 'vat': 'DE12',
                'country_id': self.env.ref('base.de').id, 'is_company': True})

    def test_checksum_error_is_rejected_with_viesac(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['res.partner'].create({'name': 'Checksum typo', 'vat': 'DE123456789',
                'country_id': self.env.ref('base.de').id, 'is_company': True})

    def test_missing_api_key_preserves_native_network_path(self):
        partner = self._partner()
        self.params.set_param('viesac.api_key', '')
        self.env.company.vat_check_vies = True
        with patch.object(NativeVatPartner, '_check_vies_iap', return_value='valid') as native:
            partner._compute_vies_valid()
        native.assert_called_once()
        self.assertTrue(partner.vies_valid)

    def test_disabled_replacement_preserves_native_path(self):
        partner = self._partner()
        self.params.set_param('viesac.replace_odoo_vies', 'False')
        with patch.object(NativeVatPartner, '_check_vies_iap', return_value='valid') as native:
            self.assertEqual(partner._check_vies_iap(), 'valid')
        native.assert_called_once()

    def test_typo_still_rejected_without_api_key(self):
        self.params.set_param('viesac.api_key', '')
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.env['res.partner'].create({'name': 'Typo', 'vat': 'DE12',
                'country_id': self.env.ref('base.de').id, 'is_company': True})
