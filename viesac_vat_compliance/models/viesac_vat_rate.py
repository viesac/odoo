# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime, timezone
from odoo import api, fields, models
from .viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL

_logger = logging.getLogger(__name__)


class ViesacVatRate(models.Model):
    _name = 'viesac.vat.rate'
    _description = 'VIESAC Global VAT Rate'
    _order = 'country_code asc'
    _sql_constraints = [('country_code_unique', 'unique(country_code)', 'Only one catalog entry per country is allowed.')]

    country_code = fields.Char(
        string='Country Code',
        size=2,
        required=True,
        index=True,
    )
    country_name = fields.Char(string='Country Name')
    tax_abbr = fields.Char(string='Tax Abbreviation', help='Official national tax name, e.g. VAT, MwSt., TVA, IVA, GST.')
    currency = fields.Char(string='Currency', size=3)
    standard_rate = fields.Float(
        string='Standard Rate (%)',
        digits=(16, 4),
        index=True,
    )
    reduced_rates_json = fields.Text(string='Reduced Rates JSON')
    special_rates_json = fields.Text(string='Special & Regional Rates JSON')
    verified_at = fields.Datetime(string='Official Verification Date')
    last_sync_at = fields.Datetime(string='Last Synchronized')

    @api.model
    def cron_sync_vat_rates(self):
        """Automated daily scheduled action to synchronize official global VAT rates."""
        self.check_access_rights('write')
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        last_etag = params.get_param('viesac.rates_etag', '')

        result = ViesacApiClient.get_vat_rates(api_key=api_key, etag=last_etag, base_url=base_url)
        if result.get('not_modified'):
            _logger.info("VIESAC VAT rates catalog is up-to-date (HTTP 304).")
            return True

        if 'error' in result:
            _logger.warning("VIESAC rates synchronization failed: %s", result.get('error'))
            return False

        payload = result.get('data') or {}
        rates_map = payload.get('data') or {}
        new_etag = result.get('etag')

        now = fields.Datetime.now()
        existing_rates = {r.country_code: r for r in self.search([])}

        for country, item in rates_map.items():
            std_rate = item.get('standard_rate')
            if std_rate is None:
                continue

            reduced_rates = [r for r in item.get('rates', []) if r.get('type') in ('reduced', 'super_reduced', 'parking')]
            special_rates = [r for r in item.get('rates', []) if r.get('type') not in ('reduced', 'super_reduced', 'parking', 'standard')]

            vals = {
                'country_code': country,
                'country_name': item.get('country_name') or country,
                'tax_abbr': item.get('tax_abbr') or 'VAT',
                'currency': item.get('currency') or '',
                'standard_rate': float(std_rate),
                'reduced_rates_json': json.dumps(reduced_rates),
                'special_rates_json': json.dumps(special_rates),
                'verified_at': self._parse_verified_at(item.get('verified_at')),
                'last_sync_at': now,
            }

            if country in existing_rates:
                existing_rates[country].write(vals)
            else:
                self.create(vals)

        if new_etag:
            params.set_param('viesac.rates_etag', new_etag)
        _logger.info("VIESAC successfully synchronized VAT rates for %s countries.", len(rates_map))
        return True

    @staticmethod
    def _parse_verified_at(value):
        if not value:
            return False
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
