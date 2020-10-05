FROM unipartdigital/odoo-tester:13.0

# Prerequisite module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i stock

# Add block_locations module
#
ADD addons /opt/odoo-addons

# Module tests
#
CMD ["--test-enable", "-i", "package_hierarchy"]
