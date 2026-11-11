FROM unipartdigital/odoo-tester:14.0_20261117

# Prerequisite module download (udes_common from udes-open)
ADD https://codeload.github.com/unipartdigital/udes-open/zip/${ODOO_VERSION} \
    /opt/udes-open.zip
RUN unzip -q -d /opt /opt/udes-open.zip && \
    ln -s /opt/udes-open-${ODOO_VERSION}/addons/udes_common \
          /opt/odoo/addons/

# Prerequisite module installation (without tests)
RUN odoo-wrapper --without-demo=all -i stock,udes_common

# Add package_hierarchy module
ADD addons /opt/odoo-addons

# Module tests
CMD ["--test-enable", "-i", "package_hierarchy"]
