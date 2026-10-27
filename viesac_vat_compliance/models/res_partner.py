# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL


class ResPartner(models.Model):
    _inherit = 'res.partner'

    viesac_vat_status = fields.Selection(
        selection=[
            ('unverified', 'Unverified'),
            ('valid', 'Valid'),
            ('limited_valid', 'Limited Valid'),
            ('pending', 'Pending Confirmation'),
            ('invalid', 'Invalid'),
            ('error', 'Check Error'),
        ],
        string='VIESAC VAT Status',
        default='unverified',
        copy=False,
        tracking=True,
    )
    viesac_official_source = fields.Char(
        string='VAT Registry Source',
        copy=False,
        help='Official government tax registry that verified this VAT number (e.g. VALID (VIES), VALID (HMRC), VALID (UID), etc.).',
    )
    viesac_consultation_number = fields.Char(
        string='VIES Consultation #',
        copy=False,
        help='Official consultation identifier provided by the European Commission VIES for tax audit defense.',
    )
    viesac_last_reference = fields.Char(
        string='VIESAC Audit Reference',
        copy=False,
    )
    viesac_last_checked_at = fields.Datetime(
        string='VAT Checked Date',
        copy=False,
    )

    viesac_eori_number = fields.Char(
        string='EORI Number',
        copy=False,
        tracking=True,
        help='Economic Operators Registration and Identification code used in customs operations.',
    )
    viesac_eori_same_as_vat = fields.Boolean(
        string='EORI Same as VAT',
        default=False,
        help='Check if the partner EORI code matches their national VAT number with country prefix.',
    )
    viesac_eori_status = fields.Selection(
        selection=[
            ('unverified', 'Unverified'),
            ('valid', 'Valid'),
            ('limited_valid', 'Limited Valid'),
            ('pending', 'Pending Confirmation'),
            ('invalid', 'Invalid'),
            ('error', 'Error'),
        ],
        string='EORI Status',
        default='unverified',
        copy=False,
        tracking=True,
    )

    viesac_audit_ids = fields.One2many(
        'viesac.audit.log',
        'partner_id',
        string='VIESAC Audits',
    )
    viesac_audit_count = fields.Integer(
        string='Audits Count',
        compute='_compute_viesac_audit_count',
    )

    @api.depends('viesac_audit_ids')
    def _compute_viesac_audit_count(self):
        for partner in self:
            partner.viesac_audit_count = len(partner.viesac_audit_ids)

    @api.onchange('viesac_eori_same_as_vat', 'vat')
    def _onchange_eori_same_as_vat(self):
        if self.viesac_eori_same_as_vat and self.vat:
            self.viesac_eori_number = self.vat

    def _get_viesac_credentials(self):
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        return api_key, base_url

    def write(self, vals):
        # Registry results describe the checked identifier, never a replacement Tax ID.
        for partner in self:
            changes = dict(vals)
            if vals.get('viesac_eori_same_as_vat'):
                changes['viesac_eori_number'] = vals.get('vat', partner.vat)
            if 'vat' in vals and vals['vat'] != partner.vat:
                changes.update(viesac_vat_status='unverified', viesac_official_source=False,
                               viesac_consultation_number=False, viesac_last_reference=False,
                               viesac_last_checked_at=False)
                if vals.get('viesac_eori_same_as_vat', partner.viesac_eori_same_as_vat):
                    changes['viesac_eori_number'] = vals['vat']
            if ('viesac_eori_number' in changes and
                    changes['viesac_eori_number'] != partner.viesac_eori_number):
                changes['viesac_eori_status'] = 'unverified'
            super(ResPartner, partner).write(changes)
        return True

    def action_verify_vat(self):
        """Verifies partner VAT number against VIESAC."""
        self.ensure_one()
        self.check_access_rights('write')
        self.check_access_rule('write')
        vat_to_check = self.vat
        if not vat_to_check:
            raise UserError('Please enter a Tax ID / VAT Number first.')

        api_key, base_url = self._get_viesac_credentials()

        # If no API key is configured, fallback to basic offline format check
        if not api_key:
            res = ViesacApiClient.basic_format_check(vat_to_check)
            if res.get('valid'):
                self.write({
                    'viesac_vat_status': 'unverified',
                    'viesac_official_source': 'FORMAT_CHECK_ONLY',
                    'viesac_last_checked_at': fields.Datetime.now(),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('VIESAC Format Valid'),
                        'message': _('Format is valid (offline check). Enter an API key in Settings to verify against live government registries.'),
                        'type': 'info',
                        'sticky': False,
                    }
                }
            self.write({
                'viesac_vat_status': 'invalid',
                'viesac_official_source': 'INVALID_FORMAT',
            })
            raise UserError(_("Invalid VAT format: %s") % res.get('error'))

        result = ViesacApiClient.validate_vat(api_key, vat_to_check, base_url=base_url)
        if 'error' in result and result.get('code') not in ('invalid_input', 'rate_limit_exceeded'):
            self.write({'viesac_vat_status': 'error'})
            raise UserError(_("Validation error from VIESAC: %s") % result.get('error'))

        status = result.get('status')
        source = result.get('source') or ''

        vals = {
            'viesac_last_checked_at': fields.Datetime.now(),
            'viesac_official_source': source,
        }

        if status == 'valid':
            vals['viesac_vat_status'] = ViesacApiClient.validation_status(result)
        elif status == 'invalid':
            vals['viesac_vat_status'] = 'invalid'
        elif status == 'audit_required':
            vals['viesac_vat_status'] = 'pending'
        else:
            vals['viesac_vat_status'] = 'error'

        self.write(vals)

        msg_type = 'success' if status == 'valid' else ('warning' if status == 'audit_required' else 'danger')
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'VAT Verification: {status.upper() if status else "DONE"}',
                'message': f"Source: {source or 'Official Registry'}",
                'type': msg_type,
                'sticky': False,
            }
        }

    def action_verify_eori(self):
        """Verifies partner EORI number."""
        self.ensure_one()
        self.check_access_rights('write')
        self.check_access_rule('write')
        eori_to_check = self.viesac_eori_number
        if not eori_to_check:
            raise UserError('Please enter an EORI Number first.')

        api_key, base_url = self._get_viesac_credentials()
        if not api_key:
            raise UserError('An active VIESAC API Key is required to verify EORI numbers in live customs registries.')

        country_code = ViesacApiClient.identifier_country(eori_to_check, self.country_id.code if self.country_id else None)
        result = ViesacApiClient.validate_eori(api_key, eori_to_check, country_code=country_code, base_url=base_url)
        if 'error' in result:
            self.write({'viesac_eori_status': 'error'})
            raise UserError(f"EORI validation error: {result.get('error')}")

        status = result.get('status')
        vals = {
            'viesac_eori_status': status if status in ('valid', 'invalid', 'limited_valid') else 'error',
        }
        self.write(vals)
        msg_type = 'success' if status == 'valid' else 'danger'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': f'EORI Verification: {status.upper() if status else "COMPLETED"}',
                'message': _("EORI %s: %s") % (eori_to_check, status or 'error'),
                'type': msg_type,
                'sticky': False,
            }
        }

    def action_verify_hybrid(self):
        """Executes full combined audit for VAT + EORI."""
        self.ensure_one()
        self.check_access_rights('write')
        self.check_access_rule('write')
        if not self.vat and not self.viesac_eori_number:
            raise UserError('Please enter at least a VAT Number or EORI Number.')

        api_key, base_url = self._get_viesac_credentials()
        if not api_key:
            raise UserError('VIESAC API key is required to create audit records.')

        audit_model = self.env['viesac.audit.log']
        audit_record = audit_model.create_or_run_audit(
            partner=self,
            audit_type='vat_eori' if (self.vat and self.viesac_eori_number) else ('eori' if self.viesac_eori_number else 'vat'),
        )
        if not audit_record:
            raise UserError(_('VIESAC could not create this audit. Check your connection, API quota and identifiers, then retry.'))
        return {
            'type': 'ir.actions.act_window',
            'name': 'VIESAC Audit Proof',
            'res_model': 'viesac.audit.log',
            'res_id': audit_record.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_viesac_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'VIESAC Audits',
            'res_model': 'viesac.audit.log',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
