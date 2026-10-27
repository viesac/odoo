# -*- coding: utf-8 -*-
import logging
import re
from urllib.parse import quote
import requests

_logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://viesac.eu'
TIMEOUT = 30


class ViesacApiClient:
    """Helper client for communicating with the VIESAC Cloud REST API v1."""

    @staticmethod
    def validation_status(data):
        status = data.get('status')
        if status == 'valid' and (data.get('registry_checked') is False or
                                  data.get('registration_valid') is False):
            return 'unverified'
        return status if status in ('valid', 'invalid') else 'pending' if status == 'audit_required' else 'error'

    @staticmethod
    def _json_response(resp, success_codes=(200,)):
        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if resp.status_code not in success_codes:
            data['error'] = data.get('error') or data.get('message') or 'VIESAC HTTP %s' % resp.status_code
            data['http_status'] = resp.status_code
        elif not data:
            data = {'error': 'Invalid JSON response from VIESAC', 'code': 'invalid_response'}
        return data

    @staticmethod
    def sanitize_vat(vat_str):
        if not vat_str:
            return ''
        cleaned = re.sub(r'[^A-Za-z0-9]', '', str(vat_str)).upper()
        return cleaned

    @classmethod
    def identifier_country(cls, value, fallback=None):
        prefix = cls.sanitize_vat(value)[:2]
        if len(prefix) == 2 and prefix.isalpha():
            return {'EL': 'GR', 'UK': 'GB'}.get(prefix, prefix)
        return fallback

    @staticmethod
    def basic_format_check(vat_str):
        """Offline format validation used when no API key is configured.

        Checks that the input starts with a 2-letter country code followed by alphanumeric characters.
        """
        cleaned = ViesacApiClient.sanitize_vat(vat_str)
        if not cleaned:
            return {'valid': False, 'error': 'Empty VAT number'}
        if len(cleaned) < 4:
            return {'valid': False, 'error': 'VAT number is too short'}
        if not re.match(r'^[A-Z]{2}[A-Z0-9]+$', cleaned):
            return {'valid': False, 'error': 'Invalid format. Must begin with a 2-letter country code.'}
        return {
            'valid': True,
            'country_code': cleaned[:2],
            'vat_number': cleaned[2:],
        }

    @classmethod
    def _headers(cls, api_key, idempotency_key=None):
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
            'X-Client': 'odoo',
            'User-Agent': 'VIESAC-Odoo/16.0',
        }
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        return headers

    @classmethod
    def get_account(cls, api_key, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        url = f'{base}/api/v1/account'
        try:
            resp = requests.get(url, headers=cls._headers(api_key), timeout=15)
            return cls._json_response(resp)
        except Exception as e:
            _logger.warning("VIESAC account fetch failed: %s", e)
            return {'error': str(e)}

    @classmethod
    def validate_vat(cls, api_key, vat_str, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        cleaned = cls.sanitize_vat(vat_str)
        url = f'{base}/api/v1/validate'
        try:
            resp = requests.get(
                url,
                params={'vat': cleaned, 'method': 'odoo'},
                headers=cls._headers(api_key),
                timeout=TIMEOUT,
            )
            return cls._json_response(resp)
        except Exception as e:
            _logger.warning("VIESAC validate_vat call failed: %s", e)
            return {'error': str(e), 'code': 'network_error'}

    @classmethod
    def validate_eori(cls, api_key, eori_str, country_code=None, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        cleaned = cls.sanitize_vat(eori_str)
        params = {'eori': cleaned, 'method': 'odoo'}
        if country_code:
            params['country_code'] = country_code.upper()
        url = f'{base}/api/v1/eori/validate'
        try:
            resp = requests.get(
                url,
                params=params,
                headers=cls._headers(api_key),
                timeout=TIMEOUT,
            )
            return cls._json_response(resp)
        except Exception as e:
            _logger.warning("VIESAC validate_eori call failed: %s", e)
            return {'error': str(e), 'code': 'network_error'}

    @classmethod
    def create_audit(cls, api_key, payload, base_url=None, idempotency_key=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        url = f'{base}/api/v1/audits'
        payload = dict(payload, method='odoo')
        headers = cls._headers(api_key, idempotency_key=idempotency_key)
        headers['Content-Type'] = 'application/json'
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
            return cls._json_response(resp, (200, 201))
        except Exception as e:
            _logger.warning("VIESAC create_audit call failed: %s", e)
            return {'error': str(e), 'code': 'network_error'}

    @classmethod
    def get_audit(cls, api_key, reference_number, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        url = f'{base}/api/v1/audits/{quote(reference_number, safe="")}'
        try:
            resp = requests.get(url, headers=cls._headers(api_key), timeout=20)
            return cls._json_response(resp)
        except Exception as e:
            _logger.warning("VIESAC get_audit call failed: %s", e)
            return {'error': str(e), 'code': 'network_error'}

    @classmethod
    def update_audit(cls, api_key, reference_number, payload, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        url = f'{base}/api/v1/audits/{quote(reference_number, safe="")}'
        headers = cls._headers(api_key)
        headers['Content-Type'] = 'application/json'
        try:
            resp = requests.put(url, json=payload, headers=headers, timeout=20)
            return cls._json_response(resp)
        except Exception as e:
            _logger.warning("VIESAC update_audit call failed: %s", e)
            return {'error': str(e), 'code': 'network_error'}

    @classmethod
    def download_certificate(cls, api_key, reference_number, cert_format='pdf', cert_type='vat', locale='en', base_url=None):
        """Downloads the official certificate file as raw bytes.

        :param cert_format: 'pdf' or 'xml'
        :param cert_type: 'vat' or 'eori'
        :param locale: one of the 23 supported ISO locales
        """
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        locale = {'cs': 'cz', 'el': 'gr'}.get(locale, locale)
        if cert_format == 'xml':
            url = f'{base}/api/v1/audits/{quote(reference_number, safe="")}/certificate/xml'
            params = {'type': cert_type}
        else:
            url = f'{base}/api/v1/audits/{quote(reference_number, safe="")}/certificate'
            params = {'type': cert_type, 'locale': locale}

        try:
            resp = requests.get(url, params=params, headers=cls._headers(api_key), timeout=25)
            if resp.status_code == 200:
                mime = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
                expected = ('application/xml', 'text/xml') if cert_format == 'xml' else ('application/pdf',)
                if mime not in expected or (cert_format == 'pdf' and not resp.content.startswith(b'%PDF-')):
                    return {'success': False, 'error': 'Unexpected certificate response format'}
                return {
                    'success': True,
                    'content': resp.content,
                    'content_type': resp.headers.get('Content-Type', 'application/octet-stream'),
                }
            return {'success': False, 'error': resp.text, 'status_code': resp.status_code}
        except Exception as e:
            _logger.warning("VIESAC certificate download failed: %s", e)
            return {'success': False, 'error': str(e)}

    @classmethod
    def get_vat_rates(cls, api_key=None, etag=None, base_url=None):
        base = (base_url or DEFAULT_BASE_URL).rstrip('/')
        url = f'{base}/api/v1/rates'
        headers = {'Accept': 'application/json', 'X-Client': 'odoo'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        if etag:
            headers['If-None-Match'] = etag
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 304:
                return {'not_modified': True}
            if resp.status_code == 200:
                data = cls._json_response(resp)
                if 'error' in data:
                    return data
                return {
                    'data': data,
                    'etag': resp.headers.get('ETag'),
                }
            return {'error': resp.text, 'status_code': resp.status_code}
        except Exception as e:
            _logger.warning("VIESAC get_vat_rates failed: %s", e)
            return {'error': str(e)}
