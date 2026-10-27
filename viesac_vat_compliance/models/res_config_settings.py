# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL

AVAILABLE_LOCALES = [
    ('en', 'English'),
    ('de', 'Deutsch (German)'),
    ('fr', 'Français (French)'),
    ('es', 'Español (Spanish)'),
    ('it', 'Italiano (Italian)'),
    ('nl', 'Nederlands (Dutch)'),
    ('pl', 'Polski (Polish)'),
    ('cz', 'Čeština (Czech)'),
    ('sk', 'Slovenčina (Slovak)'),
    ('da', 'Dansk (Danish)'),
    ('sv', 'Svenska (Swedish)'),
    ('no', 'Norsk (Norwegian)'),
    ('fi', 'Suomi (Finnish)'),
    ('pt', 'Português (Portuguese)'),
    ('ro', 'Română (Romanian)'),
    ('hu', 'Magyar (Hungarian)'),
    ('bg', 'Български (Bulgarian)'),
    ('gr', 'Ελληνικά (Greek)'),
    ('hr', 'Hrvatski (Croatian)'),
    ('sl', 'Slovenščina (Slovenian)'),
    ('lt', 'Lietuvių (Lithuanian)'),
    ('lv', 'Latviešu (Latvian)'),
    ('et', 'Eesti (Estonian)'),
]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    viesac_replace_odoo_vies = fields.Boolean(
        string='Use VIESAC for Online VAT Checks',
        config_parameter='viesac.replace_odoo_vies',
        default=True,
        help='When an API key is configured, prevent duplicate standard Odoo VIES network calls. '
             'Odoo local VAT syntax and checksum validation remains enabled. '
             'Live VIESAC checks run through Verify VAT, checkout and document audits.',
    )

    viesac_api_key = fields.Char(
        groups='base.group_system',
        string='VIESAC API Key',
        config_parameter='viesac.api_key',
        help='Your VIESAC API secret token from https://viesac.eu/app/api',
    )
    viesac_base_url = fields.Char(
        string='API Endpoint',
        config_parameter='viesac.base_url',
        default=DEFAULT_BASE_URL,
        help='VIESAC service endpoint (default: https://viesac.eu)',
    )
    viesac_certificate_locale = fields.Selection(
        selection=AVAILABLE_LOCALES,
        string='Default Certificate Language',
        config_parameter='viesac.certificate_locale',
        default='en',
        help='Official language used when generating downloadable audit PDF certificates.',
    )
    viesac_hold_deliveries = fields.Boolean(
        string='Hold Deliveries on Pending VAT',
        config_parameter='viesac.hold_deliveries',
        default=True,
        help='Temporarily block outgoing stock pickings if customer VAT verification is pending confirmation.',
    )
    viesac_vendor_bill_mode = fields.Selection(
        selection=[
            ('strict', 'Strict: Block posting vendor bill if supplier VAT is invalid'),
            ('warning', 'Warning: Allow posting with a prominent warning notice & compliance activity'),
            ('disabled', 'Disabled: Do not verify supplier VAT automatically'),
        ],
        string='Vendor Bill Protection Policy',
        config_parameter='viesac.vendor_bill_mode',
        default='warning',
        help='Protects your company input VAT deduction against invalid supplier VAT numbers upon bill confirmation.',
    )
    viesac_auto_attach_certificates = fields.Boolean(
        string='Auto-Attach PDF & XML Certificates',
        config_parameter='viesac.auto_attach_certificates',
        default=True,
        help='Automatically download PDF certificate and SHA-256 XML evidence and attach them to Orders and Invoices.',
    )
    viesac_webhook_secret = fields.Char(
        groups='base.group_system',
        string='Webhook Secret',
        config_parameter='viesac.webhook_secret',
        help='Shared secret for verifying incoming VIESAC background audit completion webhooks.',
    )

    def action_test_viesac_connection(self):
        """Tests API key and retrieves plan details."""
        self.ensure_one()
        api_key = self.viesac_api_key or self.env['ir.config_parameter'].sudo().get_param('viesac.api_key')
        base_url = self.viesac_base_url or self.env['ir.config_parameter'].sudo().get_param('viesac.base_url', DEFAULT_BASE_URL)
        if not api_key:
            raise UserError(_('Please enter a VIESAC API Key first.'))

        account = ViesacApiClient.get_account(api_key, base_url=base_url)
        if 'error' in account:
            raise UserError(_("Connection failed: %s") % account.get('error'))

        plan = account.get('plan_label') or account.get('plan') or 'Unknown'
        remaining = account.get('audit_requests_remaining', account.get('requests_remaining', 'Unlimited'))
        validations_remaining = account.get('validation_remaining_this_month', 'Unlimited')
        remaining = 'Unlimited' if remaining is None else remaining
        validations_remaining = 'Unlimited' if validations_remaining is None else validations_remaining

        msg = _(
            "VIESAC API Connected Successfully!\n\n"
            "• Plan: %s\n"
            "• Live Validations Remaining (Month): %s\n"
            "• Audit Proofs / Certificates Available: %s"
        ) % (plan, validations_remaining, remaining)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('VIESAC Connection Status'),
                'message': msg,
                'type': 'success',
                'sticky': False,
            }
        }
