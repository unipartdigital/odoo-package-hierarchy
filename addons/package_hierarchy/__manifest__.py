# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Package Hierarchy",
    "version": "11.0",
    "summary": "Inventory, Logistics, Warehousing",
    "description": "Add the ability for multi-level packages back to Odoo",
    "depends": ["stock", "udes_common"],
    "category": "Warehouse",
    "sequence": 13,
    "demo": [],
    "data": [
        "security/ir.model.access.csv",
        "views/stock_quant_package_views.xml",
        "views/stock_move_line_views.xml",
        "views/stock_picking_views.xml",
        "views/package_links.xml",
        "views/stock_warehouse.xml",
    ],
    "qweb": [],
    "test": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
