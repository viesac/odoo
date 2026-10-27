# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from .viesac_api_client import ViesacApiClient, DEFAULT_BASE_URL


class AccountMove(models.Model):
    _inherit = 'account.move'

    viesac_audit_ids = fields.One2many(
        'viesac.audit.log',
        'move_id',
        string='VIESAC Audits',
    )
    viesac_audit_count = fields.Integer(
        string='Audits Count',
        compute='_compute_viesac_audit_count',
    )
    viesac_vat_status = fields.Selection(
        selection=[('unverified', 'Unverified'), ('valid', 'Valid'), ('invalid', 'Invalid'),
                   ('pending', 'Pending'), ('limited_valid', 'Limited Valid'), ('error', 'Error')],
        compute='_compute_viesac_evidence',
        string='Partner VAT Status',
        readonly=True,
    )
    viesac_official_source = fields.Char(
        compute='_compute_viesac_evidence',
        string='Registry Source',
        readonly=True,
    )
    viesac_consultation_number = fields.Char(
        compute='_compute_viesac_evidence',
        string='VIES Consultation #',
        readonly=True,
    )
    viesac_customs_declaration_number = fields.Char(
        string='Customs Declaration № (MRN)',
        copy=False,
        help='Official customs declaration identifier for cross-border transactions.',
    )
    viesac_compliance_verified = fields.Boolean(
        string='VIESAC Audit Valid',
        default=False,
        copy=False,
        help='Indicates whether tax compliance evidence has been officially registered and attached.',
    )

    @api.depends('viesac_audit_ids')
    def _compute_viesac_audit_count(self):
        for move in self:
            move.viesac_audit_count = len(move.viesac_audit_ids)

    @api.depends('viesac_audit_ids.vat_status', 'viesac_audit_ids.official_source', 'viesac_audit_ids.consultation_number')
    def _compute_viesac_evidence(self):
        for move in self:
            audit = move.viesac_audit_ids.sorted('id', reverse=True)[:1]
            move.viesac_vat_status = audit.vat_status or 'unverified'
            move.viesac_official_source = audit.official_source
            move.viesac_consultation_number = audit.consultation_number

    def action_post(self):
        """Overrides invoice posting to register audit proof and enforce vendor bill protection."""
        res = super(AccountMove, self).action_post()

        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        base_url = params.get_param('viesac.base_url', DEFAULT_BASE_URL)
        if not api_key:
            return res

        vendor_mode = params.get_param('viesac.vendor_bill_mode', 'warning')

        for move in self:
            partner = move.partner_id
            if not partner.vat and not partner.viesac_eori_number:
                continue

            is_vendor_bill = move.move_type in ('in_invoice', 'in_refund')
            is_customer_invoice = move.move_type in ('out_invoice', 'out_refund')

            # 1. Accounts Payable (Vendor Bill) Verification
            if is_vendor_bill and vendor_mode != 'disabled':
                audit_type = 'vat_eori' if (partner.vat and partner.viesac_eori_number) else ('eori' if partner.viesac_eori_number else 'vat')
                audit = self.env['viesac.audit.log'].create_or_run_audit(
                    partner=partner,
                    invoice=move,
                    audit_type=audit_type,
                    customs_number=move.viesac_customs_declaration_number,
                )
                if audit:
                    move.viesac_compliance_verified = (audit.status == 'valid')
                    if audit.status == 'invalid':
                        if vendor_mode == 'strict':
                            raise UserError(
                                _("Vendor Bill Posting Blocked! Supplier %s has an INVALID tax ID (%s). "
                                  "Input VAT deduction cannot be legally claimed under current compliance policy.")
                                % (partner.name, partner.vat)
                            )
                        else:
                            move.activity_schedule(
                                'mail.mail_activity_data_warning',
                                summary=_('Supplier VAT Invalid on Vendor Bill'),
                                note=_("Warning: Supplier %s has an invalid tax registration (%s). Review before payment to safeguard input VAT deduction.")
                                % (partner.name, partner.vat),
                            )

            # 2. Accounts Receivable (Customer Invoice) Proof Archival
            elif is_customer_invoice:
                # Check if an audit was already created for the linked sale order
                linked_audit = False
                sale_orders = move.invoice_line_ids.mapped('sale_line_ids.order_id')
                if sale_orders:
                    so_audits = self.env['viesac.audit.log'].search([
                        ('sale_order_id', 'in', sale_orders.ids),
                        ('name', '!=', False),
                    ], order='id desc', limit=1)
                    if so_audits:
                        linked_audit = so_audits

                if linked_audit:
                    if linked_audit.partner_id != partner or linked_audit.company_id != move.company_id:
                        linked_audit = False

                if linked_audit:
                    # Idempotent update: assign invoice number to the existing audit without consuming extra credit
                    payload = {
                        'invoice_number': move.name,
                    }
                    if move.viesac_customs_declaration_number:
                        payload['customs_declaration_number'] = move.viesac_customs_declaration_number

                    result = ViesacApiClient.update_audit(api_key, linked_audit.name, payload, base_url=base_url)
                    if 'error' in result:
                        raise UserError(_('Unable to link the VIESAC audit to this invoice. Please retry.'))
                    if linked_audit.move_id and linked_audit.move_id != move:
                        linked_audit = linked_audit.copy({'name': linked_audit.name, 'move_id': move.id,
                            'pdf_attachment_id': False, 'xml_attachment_id': False,
                            'eori_pdf_attachment_id': False, 'eori_xml_attachment_id': False})
                    linked_audit.write({
                        'move_id': move.id,
                        'invoice_number': move.name,
                    })
                    if params.get_param('viesac.auto_attach_certificates', 'True') == 'True':
                        linked_audit._download_and_attach_certificates(invoice=move)
                    move.viesac_compliance_verified = linked_audit.status == 'valid'
                else:
                    # Direct invoice without prior SO audit
                    audit_type = 'vat_eori' if (partner.vat and partner.viesac_eori_number) else ('eori' if partner.viesac_eori_number else 'vat')
                    audit = self.env['viesac.audit.log'].create_or_run_audit(
                        partner=partner,
                        invoice=move,
                        audit_type=audit_type,
                        customs_number=move.viesac_customs_declaration_number,
                    )
                    if audit:
                        move.viesac_compliance_verified = (audit.status == 'valid')

        return res

    def action_view_viesac_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'VIESAC Audits',
            'res_model': 'viesac.audit.log',
            'view_mode': 'list,form',
            'domain': [('move_id', '=', self.id)],
            'context': {'default_move_id': self.id, 'default_partner_id': self.partner_id.id},
        }
