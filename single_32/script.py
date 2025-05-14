import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']
        self.device.connect(via='ssh')  # Connect using SSH
        self.parent.parameters['device'] = self.device  # Pass the device to test cases

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug aaa accounting",
            "debug tacacs events",
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
    def configure_tacacs_server(self, device):
        """Configure TACACS+ server with FQDN and enable TLS"""
        try:
            tacacs_config = [
                "tacacs server TAC",
                " address ipv4 10.76.239.47",
                " key cisco123",
                " port 6049",
                " timeout 32",
                " tls"
            ]
            device.configure(tacacs_config)

            server_group_config = [
                "aaa group server tacacs+ TAC_Grp",
                " server name TAC",
                " ip tacacs source-interface GigabitEthernet1"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ server and server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def enable_command_accounting(self, device):
        """Enable command accounting for privilege 15 commands"""
        try:
            accounting_config = [
                "aaa accounting commands 15 default start-stop group TAC_Grp"
            ]
            device.configure(accounting_config)
            logger.info("Command accounting for privilege 15 commands enabled successfully.")
        except Exception as e:
            self.failed(f"Failed to enable command accounting: {str(e)}")

    @aetest.test
    def execute_privilege_15_command(self, device):
        """Execute a privilege 15 command and verify accounting"""
        try:
            # Execute a privilege 15 command
            output = device.execute("show running-config")
            if output:
                logger.info("Privilege 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege 15 command.")
        except Exception as e:
            self.failed(f"Failed to execute privilege 15 command: {str(e)}")

    @aetest.test
    def verify_accounting_logs(self, device):
        """Verify accounting logs for privilege 15 commands"""
        try:
            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ accounting debug logs:")
            logger.info(logs)

            # Verify if accounting logs are present
            if "Accounting method=TAC_Grp" in logs:
                logger.info("Accounting is successful for privilege 15 commands.")
            else:
                self.failed("Accounting logs not found for privilege 15 commands.")
        except Exception as e:
            self.failed(f"Failed to verify accounting logs: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server TAC",
            "no aaa group server tacacs+ TAC_Grp",
            "no aaa accounting commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
