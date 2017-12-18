from odoo import models, fields
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    x_pallet_id = fields.Many2one('stock.quant.package', 'Pallet:')

    def palletise(self):
        self.ensure_one()
        if not self.x_pallet_id:
            raise UserError(_('Select a pallet.'))

        self.move_line_ids.filtered(lambda l: l.x_selected).mapped('result_package_id').write({'package_id': self.x_pallet_id.id})
        self.x_pallet_id._check_not_multi_location()
        self.move_line_ids.write({'x_selected': False})
        self.x_pallet_id = None
