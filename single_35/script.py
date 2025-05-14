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
    def configure_tacacs_servers(self, device):
        """Configure two TACACS+ servers with TLS and a server group"""
        try:
            # Configure TACACS+ server with wrong IP
            wrong_ip_config = [
                "tacacs server WRONG_IP_SERVER",
                " address ipv4 192.168.1.100",  # Wrong IP
                " key wrong_key",
                " port 6049",
                " timeout 10",
                " tls"
            ]
            device.configure(wrong_ip_config)

            # Configure TACACS+ server with correct IP
            correct_ip_config = [
                "tacacs server CORRECT_IP_SERVER",
                " address ipv4 10.76.239.47",  # Correct IP
                " key correct_key",
                " port 6049",
                " timeout 10",
                " tls"
            ]
            device.configure(correct_ip_config)

            # Configure TACACS+ server group
            server_group_config = [
                "aaa group server tacacs+ TAC_Grp",
                " server name WRONG_IP_SERVER",
                " server name CORRECT_IP_SERVER",
                " ip tacacs source-interface GigabitEthernet1"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ servers and server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ servers: {str(e)}")

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
    def verify_fallback_to_correct_server(self, device):
        """Verify fallback to the correct TACACS+ server after retries"""
        try:
            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs:")
            logger.info(logs)

            # Verify retries and fallback
            if "192.168.1.100" in logs and "10.76.239.47" in logs:
                logger.info("Request successfully retried and sent to the correct TACACS+ server.")
            else:
                self.failed("Request did not fallback to the correct TACACS+ server after retries.")
        except Exception as e:
            self.failed(f"Failed to verify fallback behavior: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server WRONG_IP_SERVER",
            "no tacacs server CORRECT_IP_SERVER",
            "no aaa group server tacacs+ TAC_Grp",
            "no aaa accounting commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
