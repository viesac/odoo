# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    viesac_audit_ids = fields.One2many(
        'viesac.audit.log',
        'purchase_order_id',
        string='VIESAC Audits',
    )
    viesac_audit_count = fields.Integer(
        string='Audits Count',
        compute='_compute_viesac_audit_count',
    )
    viesac_vendor_vat_status = fields.Selection(
        related='partner_id.viesac_vat_status',
        string='Supplier VAT Status',
        readonly=True,
    )
    viesac_customs_declaration_number = fields.Char(
        string='Customs Declaration № (MRN)',
        copy=False,
        help='Official customs declaration identifier for cross-border imports.',
    )

    @api.depends('viesac_audit_ids')
    def _compute_viesac_audit_count(self):
        for po in self:
            po.viesac_audit_count = len(po.viesac_audit_ids)

    def button_confirm(self):
        """Pre-checks supplier VAT and EORI upon purchase order confirmation."""
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        mode = params.get_param('viesac.vendor_bill_mode', 'warning')

        if api_key and mode != 'disabled':
            for po in self.filtered(lambda order: order.state in ('draft', 'sent')):
                vendor = po.partner_id
                if vendor.vat or vendor.viesac_eori_number:
                    audit_type = 'vat_eori' if (vendor.vat and vendor.viesac_eori_number) else ('eori' if vendor.viesac_eori_number else 'vat')
                    audit = self.env['viesac.audit.log'].create_or_run_audit(
                        partner=vendor,
                        purchase_order=po,
                        audit_type=audit_type,
                        customs_number=po.viesac_customs_declaration_number,
                    )
                    if audit and audit.status == 'invalid' and mode == 'strict':
                        raise UserError(
                            f"Supplier {vendor.name} has an INVALID tax registration number ({vendor.vat}) in official registries. "
                            f"Order confirmation blocked under strict compliance policy."
                        )

        return super(PurchaseOrder, self).button_confirm()

    def action_view_viesac_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'VIESAC Audits',
            'res_model': 'viesac.audit.log',
            'view_mode': 'tree,form',
            'domain': [('purchase_order_id', '=', self.id)],
            'context': {'default_purchase_order_id': self.id, 'default_partner_id': self.partner_id.id},
        }
