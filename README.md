# package_hierarchy

[![Build Status](https://travis-ci.org/unipartdigital/odoo-package-hierarchy.svg?branch=master)](https://travis-ci.org/unipartdigital/odoo-package-hierarchy)

Extend stock.quant.package model to work with parent packages, which in some cases is needed when working with packages inside pallets.

## Features of this module

This module adds the following features:
* Ability to set the parent package of a package
* Ability to move a package into another package when a stock.picking is done
* Check that all the content of a parent package is in the same location


## To change
* Change fields x_field_name to u_field_name
* Stock.quant.packge has a field name called parent_ids but in the compute function uses ancestor_ids
* Parent package is only shonw at package view if it is set, change it to be able to set it when it is emptye
* Packages button (top right of stock.picking.form view) only shows packages, update it to also show parent packages
* x_selected still needed? Probably we can remove it and add it later if we need to palletise using UI
