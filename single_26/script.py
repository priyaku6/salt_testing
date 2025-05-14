import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']  # Replace with the correct device name
        self.device.connect(via='ssh')  # Connect using SSH
        self.parent.parameters['device'] = self.device  # Pass the device to test cases
        logger.info(f"Connected to device: {self.device.name}")

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug aaa authentication",
            "debug aaa authorization",
            "debug aaa accounting",
            "debug tacacs events",
            "debug tacacs authentication",
            "debug tacacs accounting",
            "debug ssl"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def verify_fallback_to_non_tls(self, device):
        """Verify the request is triggered to the Non-TLS server group when TLS servers are not responding"""
        try:
            # Simulate TLS server failure
            device.configure("no tacacs server TLS1")
            device.configure("no tacacs server TLS2")

            # Execute a privilege level 15 command
            output = device.execute("show running-config")
            if output:
                logger.info("Privilege level 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege level 15 command.")

            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs:")
            logger.info(logs)

            # Verify if the request is sent to the Non-TLS server group
            if "Accounting method=NON_TLS_GROUP" in logs:
                logger.info("Request is correctly triggered to the Non-TLS server group.")
            else:
                self.failed("Request is not triggered to the Non-TLS server group when TLS servers are not responding.")
        except Exception as e:
            self.failed(f"Failed to verify fallback behavior: {str(e)}")

    @aetest.cleanup
    def cleanup(self, device):
        """Re-enable TLS servers and clean up configuration"""
        try:
            device.configure("tacacs server TLS1")
            device.configure("tacacs server TLS2")
            logger.info("Re-enabled TLS servers.")
        except Exception as e:
            logger.warning(f"Failed to re-enable TLS servers: {str(e)}")
