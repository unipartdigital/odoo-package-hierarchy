FROM mcb30/odoo-tester

# Prerequisite module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i stock

# Add block_locations module
#
ADD addons /opt/odoo-addons

# Module tests
#
CMD ["--test-enable", "-i", "package_hierarchy"]
