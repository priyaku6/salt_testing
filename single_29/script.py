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
            "debug ssl errors"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_servers(self, device):
        """Configure TACACS+ servers and server groups"""
        try:
            # Configure Non-TLS TACACS+ servers
            nontls_config = [
                "tacacs server NON_TLS1",
                " address ipv4 192.168.2.1",
                " key nontls_key1",
                " timeout 5",
                " port 49",
                "tacacs server NON_TLS2",
                " address ipv4 192.168.2.2",
                " key nontls_key2",
                " timeout 5",
                " port 49"
            ]
            device.configure(nontls_config)

            # Configure TLS-supported TACACS+ servers
            tls_config = [
                "tacacs server TLS1",
                " address ipv4 192.168.1.1",
                " key tls_key1",
                " timeout 5",
                " port 6049",
                " tls",
                "tacacs server TLS2",
                " address ipv4 192.168.1.2",
                " key tls_key2",
                " timeout 5",
                " port 6049",
                " tls"
            ]
            device.configure(tls_config)

            # Configure TACACS+ server groups
            server_group_config = [
                "aaa group server tacacs+ NON_TLS_GROUP",
                " server name NON_TLS1",
                " server name NON_TLS2",
                "aaa group server tacacs+ TLS_GROUP",
                " server name TLS1",
                " server name TLS2"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ servers and server groups configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ servers: {str(e)}")

    @aetest.test
    def configure_accounting(self, device):
        """Enable accounting for privilege level 15 commands"""
        try:
            # Configure accounting
            accounting_config = [
                "aaa accounting commands 15 default start-stop group NON_TLS_GROUP group TLS_GROUP"
            ]
            device.configure(accounting_config)
            logger.info("Accounting configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure accounting: {str(e)}")

    @aetest.test
    def execute_privilege_15_commands(self, device):
        """Execute privilege level 15 commands and verify accounting"""
        try:
            # Execute a privilege level 15 command
            output = device.execute("show running-config")
            if output:
                logger.info("Privilege level 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege level 15 command.")

            # Verify accounting logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ accounting logs:")
            logger.info(logs)

            if "Accounting" in logs or "ACCT" in logs:
                logger.info("Accounting is successful.")
            else:
                self.failed("Accounting logs not found.")
        except Exception as e:
            self.failed(f"Failed to execute commands or verify accounting: {str(e)}")

    @aetest.test
    def verify_fallback_to_tls(self, device):
        """Verify the request is triggered to the TLS server group when Non-TLS servers are not responding"""
        try:
            # Simulate Non-TLS server failure
            device.configure("no tacacs server NON_TLS1")
            device.configure("no tacacs server NON_TLS2")

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

            # Verify if the request is sent to the TLS server group
            if "TLS_GROUP" in logs:
                logger.info("Request is correctly triggered to the TLS server group.")
            else:
                self.failed("Request is not triggered to the TLS server group when Non-TLS servers are not responding.")
        except Exception as e:
            self.failed(f"Failed to verify fallback behavior: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server NON_TLS1",
            "no tacacs server NON_TLS2",
            "no tacacs server TLS1",
            "no tacacs server TLS2",
            "no aaa group server tacacs+ NON_TLS_GROUP",
            "no aaa group server tacacs+ TLS_GROUP",
            "no aaa accounting commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
