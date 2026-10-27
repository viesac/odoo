import time

from odoo import http
from odoo.http import request
from odoo.addons.viesac_vat_compliance.models.viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL


class ViesacWebsiteSaleController(http.Controller):
    @http.route('/viesac/checkout/validate_vat', type='json', auth='public', website=True, methods=['POST'])
    def validate_checkout_vat(self, vat=None, country_id=None, **kwargs):
        # Informational validation only. Odoo's configured tax rules determine taxes
        # from the saved billing/shipping addresses at checkout submission.
        order = request.website.sale_get_order()
        if not order or order.state != 'draft' or not order.order_line:
            return {'valid': False, 'status': 'unavailable'}
        if not isinstance(vat, str) or len(vat) > 40:
            return {'valid': False, 'status': 'invalid'}
        vat = ViesacApiClient.sanitize_vat(vat)
        if not vat:
            return {'valid': False, 'status': 'empty'}
        cache = request.session.get('viesac_vat_cache', {})
        now = time.time()
        entry = cache.get(vat)
        if entry and entry['result'].get('status') in ('valid', 'invalid') and now - entry['at'] < 300:
            return entry['result']
        attempts = [t for t in request.session.get('viesac_vat_attempts', []) if now - t < 60]
        if len(attempts) >= 5:
            return {'valid': False, 'status': 'rate_limited'}
        request.session['viesac_vat_attempts'] = attempts + [now]
        params = request.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        if not api_key:
            result = ViesacApiClient.basic_format_check(vat)
            return {'valid': False, 'format_valid': result.get('valid', False),
                    'status': 'unverified' if result.get('valid') else 'invalid'}
        result = ViesacApiClient.validate_vat(api_key, vat, base_url=base_url)
        status = ViesacApiClient.validation_status(result)
        response = {'valid': status == 'valid', 'status': status, 'source': result.get('source')}
        # Never return company details from a quick validation.
        cache = {k: v for k, v in cache.items() if now - v['at'] < 300}
        if status in ('valid', 'invalid'):
            cache[vat] = {'at': now, 'result': response}
        request.session['viesac_vat_cache'] = cache
        return response
