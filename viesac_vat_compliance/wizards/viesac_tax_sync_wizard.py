# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError

EU_MEMBER_CODES = [
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'ES', 'FI',
    'FR', 'GR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
]


class ViesacTaxSyncWizard(models.TransientModel):
    _name = 'viesac.tax.sync.wizard'
    _description = 'VIESAC Tax Rate Assistant & Fiscal Position Synchronizer'

    action_type = fields.Selection(
        selection=[
            ('company_standard', 'Add Standard VAT Rate for Store/Company Country'),
            ('eu_oss', 'Review EU Destination Rates for OSS Setup'),
            ('safe_rollover', 'Review Existing Company Taxes (No Automatic Changes)'),
        ],
        string='Sync Operation',
        default='company_standard',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    def action_execute_tax_sync(self):
        self.ensure_one()
        if self.company_id not in self.env.companies:
            raise UserError('Select a company available in the current session.')
        self = self.with_company(self.company_id)
        # Ensure rates catalog is populated
        rate_model = self.env['viesac.vat.rate']
        if not rate_model.search_count([]):
            rate_model.cron_sync_vat_rates()

        if self.action_type == 'company_standard':
            return self._sync_company_standard_rate()
        elif self.action_type == 'eu_oss':
            return self._configure_eu_oss()
        elif self.action_type == 'safe_rollover':
            return self._execute_safe_rollover()

    def _sync_company_standard_rate(self):
        country = self.company_id.country_id
        if not country or not country.code:
            raise UserError('Your company does not have a country configured.')

        rate_rec = self.env['viesac.vat.rate'].search([('country_code', '=', country.code.upper())], limit=1)
        if not rate_rec:
            raise UserError(f"No official VIESAC VAT rate record found for country {country.code}.")

        tax_model = self.env['account.tax']
        existing_tax = tax_model.search([
            ('company_id', '=', self.company_id.id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', rate_rec.standard_rate),
            ('amount_type', '=', 'percent'),
            ('country_id', '=', country.id),
        ], limit=1)

        if existing_tax:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Standard Rate Exists',
                    'message': f"A standard tax rate of {rate_rec.standard_rate}% already exists for {country.name}.",
                    'type': 'info',
                }
            }

        tax_name = f"{rate_rec.tax_abbr or 'VAT'} {rate_rec.standard_rate:.1f}% ({country.code})"
        new_tax = tax_model.create({
            'name': tax_name,
            'amount_type': 'percent',
            'amount': rate_rec.standard_rate,
            'type_tax_use': 'sale',
            'country_id': country.id,
            'company_id': self.company_id.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Standard Rate Added',
                'message': f"Created tax '{new_tax.name}' based on official VIESAC catalog ({rate_rec.standard_rate}%).",
                'type': 'success',
            }
        }

    def _configure_eu_oss(self):
        # Destination rates are reference data. OSS reporting grids, tax mappings,
        # product categories and fiscal positions belong to Odoo's localization.
        return {
            'type': 'ir.actions.act_window',
            'name': 'EU VAT Rates - Configure OSS with Your Accounting Localization',
            'res_model': 'viesac.vat.rate',
            'view_mode': 'list,form',
            'domain': [('country_code', 'in', EU_MEMBER_CODES)],
        }

    def _execute_safe_rollover(self):
        # Never guess a standard tax from the first active tax: it can be a reduced
        # rate or carry reporting tags and product/fiscal-position references.
        return {
            'type': 'ir.actions.act_window',
            'name': 'Review Company Taxes Against the VIESAC Catalog',
            'res_model': 'account.tax',
            'view_mode': 'list,form',
            'domain': [('company_id', '=', self.company_id.id)],
            'context': {'default_company_id': self.company_id.id},
        }
