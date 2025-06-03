import subprocess
import re
import logging

from pyats import aetest  # type: ignore
from pyats.log.utils import banner  # type: ignore

logger = logging.getLogger(__name__)


class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_topology(self, testbed):
        """Validate the testbed information"""
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        """Initialize test variables with defaults if not found in testbed"""
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut

        # Define default values for all required variables
        defaults = {
            'working_tacacs_server': "TACACS_WORKING",
            'nonworking_tacacs_server': "TACACS_NONWORKING",
            'tacacs_working_group': "TACACS_WORK_GROUP",
            'tacacs_nonworking_group': "TACACS_NOWORK_GROUP",
            'tacacs_port': "49",
            'tacacs_key': "cisco123",
            'tacacs_ip_working': "10.1.1.1",
            'tacacs_ip_nonworking': "192.168.254.254",  # Non-routable address
            'ssh_username': "test_user",
            'ssh_password': "test_password",
            'source_interface': "GigabitEthernet1"
        }

        # Get device IP from testbed if available, else use default
        try:
            testscript.parameters['device_ip'] = uut.connections.a.ip
        except AttributeError:
            testscript.parameters['device_ip'] = "10.76.239.45"  # Default value

        # Safely get variables from testbed or use defaults
        for var_name, default_value in defaults.items():
            try:
                testscript.parameters[var_name] = uut.custom.get(var_name, default_value)
            except (AttributeError, KeyError):
                testscript.parameters[var_name] = default_value
                logger.info(f"Using default value for {var_name}: {default_value}")

        # Save initial configuration for restoration
        testscript.parameters['initial_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        try:
            uut.connect()
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
        except Exception as e:
            self.failed(f"Failed to connect to device: {str(e)}")

    @aetest.subsection
    def save_initial_config(self, uut, testscript):
        """Save the initial configuration for later restoration"""
        logger.info(banner("Saving initial configuration..."))
        testscript.parameters['initial_config'] = uut.execute("show running-config | include aaa|tacacs")


class TacacsServerGroupFailoverTest(aetest.Testcase):
    """Test case to verify TACACS server group failover functionality"""

    @aetest.setup
    def setup(self, uut):
        """Enable required services and settings"""
        logger.info(banner("Setting up test prerequisites"))

        # Enable terminal PRC exposure
        logger.info("Enabling PRC exposure")
        output = uut.execute("terminal prc expose")
        if "Error" in output:
            logger.warning("PRC exposure command returned an error, but continuing")

        # Enable AAA new-model
        logger.info("Enabling AAA new-model")
        try:
            uut.api.configure_aaa_new_model()
        except Exception as e:
            logger.warning(f"Error with AAA new-model API, using direct configuration: {str(e)}")
            uut.configure("aaa new-model")

        # Enable service internal if needed for debugging
        logger.info("Enabling service internal")
        uut.configure("service internal")

    # Other test cases remain unchanged, except for certificate-related logic removed

