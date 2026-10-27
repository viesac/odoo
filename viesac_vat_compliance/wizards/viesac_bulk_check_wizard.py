# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class ViesacBulkCheckWizard(models.TransientModel):
    _name = 'viesac.bulk.check.wizard'
    _description = 'VIESAC Bulk Partner Verification Wizard'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Selected Partners',
        default=lambda self: self.env.context.get('active_ids', []),
    )
    total_partners = fields.Integer(
        string='Total Partners',
        compute='_compute_total',
    )
    check_type = fields.Selection(
        selection=[
            ('validate', 'Live Validation (Update VAT and EORI Status)'),
            ('audit', 'Full Audit (Credits and Certificate Access Follow Your API Plan)'),
        ],
        string='Verification Mode',
        default='validate',
        required=True,
    )

    @api.depends('partner_ids')
    def _compute_total(self):
        for w in self:
            w.total_partners = len(w.partner_ids)

    def action_process_bulk_check(self):
        self.ensure_one()
        partners = self.partner_ids.filtered(lambda p: bool(p.vat or p.viesac_eori_number))
        if not partners:
            raise UserError('None of the selected partners have a VAT number or EORI number.')

        valid_count = 0
        invalid_count = 0
        error_count = 0

        for p in partners:
            try:
                if self.check_type == 'validate':
                    if p.vat:
                        p.action_verify_vat()
                    if p.viesac_eori_number:
                        p.action_verify_eori()
                else:
                    audit_type = 'vat_eori' if (p.vat and p.viesac_eori_number) else ('eori' if p.viesac_eori_number else 'vat')
                    self.env['viesac.audit.log'].create_or_run_audit(partner=p, audit_type=audit_type)

                statuses = ([p.viesac_vat_status] if p.vat else []) + ([p.viesac_eori_status] if p.viesac_eori_number else [])
                if statuses and all(status == 'valid' for status in statuses):
                    valid_count += 1
                elif 'invalid' in statuses:
                    invalid_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        msg = (
            f"Bulk Verification Completed for {len(partners)} partners:\n\n"
            f"• Valid: {valid_count}\n"
            f"• Invalid: {invalid_count}\n"
            f"• Pending/Error: {error_count}"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'VIESAC Bulk Verification Result',
                'message': msg,
                'type': 'success' if invalid_count == 0 and error_count == 0 else 'warning',
                'sticky': True,
            }
        }
