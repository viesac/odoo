# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    viesac_audit_ids = fields.One2many(
        'viesac.audit.log',
        'sale_order_id',
        string='VIESAC Audits',
    )
    viesac_audit_count = fields.Integer(
        string='Audits Count',
        compute='_compute_viesac_audit_count',
    )
    viesac_vat_status = fields.Selection(
        related='partner_id.viesac_vat_status',
        string='Customer VAT Status',
        readonly=True,
    )
    viesac_customs_declaration_number = fields.Char(
        string='Customs Declaration № (MRN)',
        copy=False,
        help='Official customs declaration identifier (e.g. for cross-border exports).',
    )
    viesac_delivery_held = fields.Boolean(
        string='Delivery Held (VIESAC)',
        default=False,
        copy=False,
        help='Set to true if order delivery is temporarily held pending government VAT confirmation.',
    )

    @api.depends('viesac_audit_ids')
    def _compute_viesac_audit_count(self):
        for order in self:
            order.viesac_audit_count = len(order.viesac_audit_ids)

    def action_confirm(self):
        """Overrides order confirmation to run VIESAC audit and check delivery hold policy."""
        orders_to_check = self.filtered(lambda order: order.state in ('draft', 'sent'))
        res = super(SaleOrder, self).action_confirm()

        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('viesac.api_key', '')
        if not api_key:
            return res

        for order in orders_to_check:
            partner = order.partner_id
            if not partner.vat and not partner.viesac_eori_number:
                continue

            # Determine audit type
            audit_type = 'vat_eori' if (partner.vat and partner.viesac_eori_number) else ('eori' if partner.viesac_eori_number else 'vat')

            audit = self.env['viesac.audit.log'].create_or_run_audit(
                partner=partner,
                order=order,
                audit_type=audit_type,
                customs_number=order.viesac_customs_declaration_number,
            )

            # Check delivery hold policy
            hold_enabled = params.get_param('viesac.hold_deliveries', 'True') == 'True'
            if hold_enabled and audit and audit.status in ('pending', 'limited_valid'):
                order.viesac_delivery_held = True
                order.message_post(
                    body="<b>VIESAC Notice:</b> Order delivery is held on status PENDING/LIMITED VALID until government VAT verification completes.",
                    message_type='notification',
                )

        return res

    def action_view_viesac_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'VIESAC Audits',
            'res_model': 'viesac.audit.log',
            'view_mode': 'list,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id, 'default_partner_id': self.partner_id.id},
        }
