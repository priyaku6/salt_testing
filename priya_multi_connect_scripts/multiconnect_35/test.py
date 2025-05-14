import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device"""
        # Use the correct device name from the testbed.yaml file
        self.parent.parameters['uut'] = testbed.devices['vwlc-ksukulka']  # Replace 'vwlc-ksukulka' with your device name
        uut = self.parent.parameters['uut']

        try:
            uut.connect()
            logger.info("Successfully connected to the device.")
        except Exception as e:
            self.failed(f"Failed to connect to the device: {e}")

class TacacsVerification(aetest.Testcase):
    """Testcase to verify TACACS+ configuration"""

    @aetest.setup
    def setup(self):
        """Enable debugging for TACACS+"""
        uut = self.parent.parameters['uut']
        uut.execute("debug tacacs authentication")
        uut.execute("debug tacacs accounting")
        logger.info("Enabled TACACS+ debugging.")

    @aetest.test
    def verify_tacacs_server(self):
        """Verify TACACS+ server configuration"""
        uut = self.parent.parameters['uut']
        output = uut.execute("show running-config | include tacacs server")
        logger.info(f"TACACS+ server configuration:\n{output}")

        if "NonTLS_Server1" not in output:
            self.failed("TACACS+ server 'NonTLS_Server1' is not configured.")

    @aetest.test
    def verify_tacacs_group(self):
        """Verify TACACS+ server group configuration"""
        uut = self.parent.parameters['uut']
        output = uut.execute("show running-config | section aaa group server tacacs+")
        logger.info(f"TACACS+ server group configuration:\n{output}")

        if "NonTLS_Group" not in output or "NonTLS_Server1" not in output:
            self.failed("TACACS+ server group 'NonTLS_Group' is not properly configured.")

    @aetest.test
    def verify_aaa_configuration(self):
        """Verify AAA configuration"""
        uut = self.parent.parameters['uut']
        output = uut.execute("show running-config | section aaa")
        logger.info(f"AAA configuration:\n{output}")

        required_config = [
            "aaa authentication login default group NonTLS_Group local",
            "aaa authorization exec default group NonTLS_Group local",
            "aaa authorization commands 15 default group NonTLS_Group local",
            "aaa accounting commands 15 default start-stop group NonTLS_Group"
        ]

        for config in required_config:
            if config not in output:
                self.failed(f"Missing AAA configuration: {config}")

    @aetest.test
    def verify_tacacs_connectivity(self):
        """Verify connectivity to the TACACS+ server"""
        uut = self.parent.parameters['uut']
        output = uut.execute("ping 10.76.239.180")  # Replace with your TACACS+ server IP
        logger.info(f"Ping output:\n{output}")

        if "!!!!" not in output:
            self.failed("TACACS+ server is not reachable.")

    @aetest.test
    def verify_debug_logs(self):
        """Check debug logs for TACACS+ errors"""
        uut = self.parent.parameters['uut']
        output = uut.execute("show logging | include TACACS")
        logger.info(f"Debug logs:\n{output}")

        if "Authentication failed" in output or "Authorization failed" in output:
            self.failed("TACACS+ authentication or authorization failed. Check server configuration and credentials.")

    @aetest.cleanup
    def cleanup(self):
        """Disable debugging"""
        uut = self.parent.parameters['uut']
        uut.execute("undebug all")
        logger.info("Disabled all debugging.")

class CommonCleanup(aetest.CommonCleanup):
    """Common cleanup tasks"""

    @aetest.subsection
    def disconnect_from_device(self):
        """Disconnect from the device"""
        uut = self.parent.parameters['uut']
        uut.disconnect()
        logger.info("Disconnected from the device.")
