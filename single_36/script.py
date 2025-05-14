import logging
from pyats import aetest
from pyats.log.utils import banner
import time

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']
        self.device.connect(via='ssh')  # Connect using SSH
        self.parent.parameters['device'] = self.device  # Pass the device to test cases
        logger.info("Connected to the device successfully.")

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
            "debug tacacs accounting",
            "debug ssl openssl"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_server(self, device):
        """Configure TACACS+ server with ideal timeout and create server group"""
        try:
            # Remove incorrect TACACS+ server configurations
            cleanup_cmds = [
                "no tacacs server TAC",
                "no aaa group server tacacs+ TAC_Grp",
                "no aaa accounting commands 15 default"
            ]
            device.configure(cleanup_cmds)

            # Configure the correct TACACS+ server
            tacacs_config = [
                "tacacs server TAC",
                " address ipv4 10.76.239.47",
                " key cisco123",
                " port 6049",
                " timeout 60",
                " tls"
            ]
            device.configure(tacacs_config)

            # Create a TACACS+ server group
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
        """Enable command accounting with the created TACACS+ group"""
        try:
            accounting_config = [
                "aaa accounting commands 15 default start-stop group TAC_Grp"
            ]
            device.configure(accounting_config)
            logger.info("Command accounting enabled successfully.")
        except Exception as e:
            self.failed(f"Failed to enable command accounting: {str(e)}")

    @aetest.test
    def execute_privilege_15_clis(self, device):
        """Execute privilege 15 CLIs and verify accounting request"""
        try:
            # Execute a privilege 15 command
            output = device.execute("show version")
            if output:
                logger.info("Privilege 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege 15 command.")

            # Verify accounting request in debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs after command execution:")
            logger.info(logs)

            if "Accounting method=TAC_Grp" in logs and "Accounting response status = SUCCESS" in logs:
                logger.info("Accounting request sent and successful.")
            else:
                self.failed("Accounting request failed or not sent.")
        except Exception as e:
            self.failed(f"Failed to execute privilege 15 command: {str(e)}")

    @aetest.test
    def wait_and_verify_tcp_connection_closed(self, device):
        """Wait for 60 seconds and verify TCP connection is closed"""
        try:
            logger.info("Waiting for 60 seconds...")
            time.sleep(60)

            # Verify TCP connection is closed
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs after waiting:")
            logger.info(logs)

            if "TACACS SECURE connection closed" in logs:
                logger.info("TCP connection closed successfully after timeout.")
            else:
                self.failed("TCP connection not closed after timeout.")
        except Exception as e:
            self.failed(f"Failed to verify TCP connection closure: {str(e)}")

    @aetest.test
    def execute_privilege_15_clis_again(self, device):
        """Execute privilege 15 CLIs again and verify new TCP connection"""
        try:
            # Execute a privilege 15 command
            output = device.execute("show version")
            if output:
                logger.info("Privilege 15 command executed successfully again.")
            else:
                self.failed("Failed to execute privilege 15 command again.")

            # Verify new TCP connection and accounting logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs after new command execution:")
            logger.info(logs)

            if "TACACS SECURE connection established" in logs and "Accounting method=TAC_Grp" in logs:
                logger.info("New TCP connection established and accounting request successful.")
            else:
                self.failed("New TCP connection not established or accounting request failed.")
        except Exception as e:
            self.failed(f"Failed to execute privilege 15 command again: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server TAC",
            "no aaa group server tacacs+ TAC_Grp",
            "no aaa accounting commands 15 default",
            "undebug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
