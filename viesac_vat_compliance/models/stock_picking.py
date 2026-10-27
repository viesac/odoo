from odoo import models, _
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        for picking in self:
            if picking.picking_type_code == 'outgoing' and picking.sale_id.viesac_delivery_held:
                raise UserError(_('Delivery is held until VIESAC confirms the customer VAT registration.'))
        return super()._action_done()
