# package_hierarchy

[![Build Status](https://travis-ci.org/unipartdigital/odoo-package-hierarchy.svg?branch=13.0)](https://travis-ci.org/unipartdigital/odoo-package-hierarchy)

Extend stock.quant.package model to work with parent packages, which in some cases is needed when working with packages inside pallets.

## Features of this module

This module adds the following features:

* Ability to set the parent package of a package.
* Ability to move a package into another package when a stock.picking is done.
* Check that all the content of a parent package is in the same location.
* Ability to set the maximum permitted depth of packages.

## To change

* Packages button (top right of stock.picking.form view) only the related packages, this could be
updated to also show their parent packages.
* Clean-up of links either after relevant move lines/moves have been completed or periodically.
Alternatively might want to keep them (at least for some time) for traceability.
* Look at optimizing package move/movelines if all of parent is in the picking.
* Move stuff from models/model.py into repo odoo-core-enhancements so we don't need the error flag.
* Decide if further checks in validate links are neccesary or if they would degrade performance
too much to be useful.
