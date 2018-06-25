# -*- coding: utf-8 -*-

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    x_selected = fields.Boolean(string=' ', help='Check this box to select')

    u_result_parent_package_id = fields.Many2one('stock.quant.package',
                    'Parent Destination Package', ondelete='restrict')

    def _action_done(self):
        """ When a move_line is done and it has result_package_id its
            parent will be removed if u_result_parent_package_id is empty,
            otherwise it will be updated to be u_result_parent_package_id.
        """
        super(StockMoveLine, self)._action_done()

        for ml in self:
            result_parent = ml.u_result_parent_package_id
            result_package = ml.result_package_id
            if result_parent:
                if result_package:
                    # only update if it is different
                    if result_package.package_id != result_parent:
                        result_package.package_id = result_parent
                else:
                    raise ValidationError(
                            _('Result parent package without result'
                              ' package at picking %s') % ml.picking_id.name)
            else:
                if result_package and result_package.package_id:
                    result_package.package_id = False

    @api.onchange('result_package_id')
    def onchange_result_package(self):
        """ Remove the result parent package when result package is empty.
            In order this to work parent package field cannot be readonly.
        """
        if not self.result_package_id and self.u_result_parent_package_id:
            self.u_result_parent_package_id = False

    @api.constrains('u_result_parent_package_id')
    @api.onchange('u_result_parent_package_id')
    def _assert_one_parent_package(self):
        """ Checks that there is only one parent package per result_package_id
            and that there is result_package_id
        """
        for ml in self:
            result_parent = ml.u_result_parent_package_id
            if result_parent:
                result_package = ml.result_package_id
                if not result_package:
                    raise ValidationError(_('Cannot set result parent package to a move line without result package.'))
                # get lines with the same result_package_id that have u_result_parent_package_id
                lines = ml.picking_id.mapped('move_line_ids').filtered(lambda l: l.result_package_id == result_package and
                                                                                 l.u_result_parent_package_id)
                parents = lines.mapped('u_result_parent_package_id')
                if len(parents) > 1:
                    raise ValidationError(
                            _('Multiple result parent packages for package %s found %s.') %
                                (result_package.name, ' '.join(parents.mapped('name')))
                            )
