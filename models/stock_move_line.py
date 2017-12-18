from odoo import models, fields


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    x_selected = fields.Boolean(string=' ', help='Check this box to select')
