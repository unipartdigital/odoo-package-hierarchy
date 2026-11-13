FROM unipartdigital/udes-tester:14.0

# Prerequisite module download (udes_common from udes-open)
ADD https://codeload.github.com/unipartdigital/udes-open/zip/${ODOO_VERSION} \
    /opt/udes-open.zip
USER root
RUN unzip -q -d /opt /opt/udes-open.zip ; \
    ln -s /opt/udes-open-${ODOO_VERSION}/addons/udes_common \
          /opt/odoo/addons/

# Install pip packages
USER odoo
RUN pip3 install --user coverage==4.5.1

# Prerequisite module installation (without tests)
USER root
RUN odoo-wrapper --without-demo=all -i stock,udes_common

# Add package_hierarchy module
ADD addons /opt/odoo-addons

# Module tests
CMD ["--test-enable", "-i", "package_hierarchy"]
