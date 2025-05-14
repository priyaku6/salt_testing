import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']  # Use the correct hostname
        self.device.connect(via='telnet')  # Explicitly specify the connection method
        self.parent.parameters['device'] = self.device  # Pass the device to test cases

    @aetest.subsection
    def save_initial_config(self, device):
        """Save initial configuration"""
        self.initial_config = device.execute('show running-config')

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug tacacs accounting",
            "debug tacacs events",
            "debug ssl openssl errors",
            "debug ssl openssl msg"
        ]
        for cmd in debug_commands:
            device.execute(cmd)
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_servers(self, device):
        """Configure two TACACS+ servers (TLS and Non-TLS)"""
        try:
            # Configure TLS-enabled TACACS+ server
            tls_config = [
                "tacacs server TLS_SERVER",
                " address ipv4 192.168.2.2",
                " key cisco123",
                " tls",
                " tls port 49"
            ]
            device.configure(tls_config)

            # Configure Non-TLS TACACS+ server
            nontls_config = [
                "tacacs server NonTLS_SERVER",
                " address ipv4 192.168.2.1",
                " key cisco123"
            ]
            device.configure(nontls_config)

            # Configure TACACS+ server group
            server_group_config = [
                "aaa group server tacacs+ TACACS_GROUP",
                " server name TLS_SERVER",
                " server name NonTLS_SERVER"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ servers and server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ servers: {str(e)}")

    @aetest.test
    def enable_accounting(self, device):
        """Enable accounting for privilege 15 with TACACS+ group"""
        try:
            accounting_config = [
                "aaa accounting exec default start-stop group TACACS_GROUP",
                "aaa accounting commands 15 default start-stop group TACACS_GROUP"
            ]
            device.configure(accounting_config)
            logger.info("Accounting configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure accounting: {str(e)}")

    @aetest.test
    def execute_privilege_15_command(self, device):
        """Execute a privilege 15 CLI command and verify accounting"""
        try:
            # Execute a privilege 15 command
            device.execute("show running-config")

            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs:")
            logger.info(logs)

            # Verify if the request is not sent to the Non-TLS server
            if "192.168.2.1" in logs:
                self.failed("Request is incorrectly triggered to the Non-TLS server.")
            else:
                logger.info("Request is not triggered to the Non-TLS server when the TLS server is not responding.")
        except Exception as e:
            self.failed(f"Failed to execute privilege 15 command: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server TLS_SERVER",
            "no tacacs server NonTLS_SERVER",
            "no aaa group server tacacs+ TACACS_GROUP",
            "no aaa accounting exec default",
            "no aaa accounting commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
