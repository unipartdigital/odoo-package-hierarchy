# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Package Hierarchy',
    'version': '11',
    'summary': 'Inventory, Logistics, Warehousing',
    'description': "Add the ability for multi-level packages back to Odoo",
    'depends': ['stock'],
    'category': 'Warehouse',
    'sequence': 13,
    'demo': [
    ],
    'data': [
        'views/stock_quant_views.xml',
        'views/stock_picking_views.xml',
    ],
    'qweb': [
    ],
    'test': [
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
