import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        retries = 3
        for attempt in range(retries):
            try:
                self.device = testbed.devices['vwlc-ksukulka']  # Replace with the correct device name
                self.device.connect(via='ssh', timeout=60)  # Increased timeout to 60 seconds
                self.parent.parameters['device'] = self.device  # Pass the device to test cases
                self.parent.parameters['custom'] = self.device.custom  # Pass custom attributes
                logger.info(f"Connected to device: {self.device.name}")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < retries - 1:
                    continue
                else:
                    self.failed(f"Failed to connect to device after {retries} attempts.")

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug aaa authentication",
            "debug aaa authorization",
            "debug tacacs events",
            "debug tacacs authentication",
            "debug ssl errors"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd, timeout=60)  # Increased timeout to 60 seconds
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_server(self, device, custom):
        """Configure TACACS+ server with TLS"""
        try:
            tacacs_config = [
                f"tacacs server {custom['tacacs_server_name']}",
                f" address ipv4 {custom['tacacs_ip']}",
                f" key cisco123",  # Replace with the actual key if needed
                f" timeout {custom['tls_connection_timeout']}",
                f" port {custom['tls_port']}",
                " tls"
            ]
            device.configure(tacacs_config, timeout=60)  # Increased timeout to 60 seconds
            logger.info("TACACS+ server configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def configure_server_group(self, device, custom):
        """Configure TACACS+ server group"""
        try:
            server_group_config = [
                f"aaa group server tacacs+ {custom['tacacs_server_group']}",
                f" server name {custom['tacacs_server_name']}"
            ]
            device.configure(server_group_config, timeout=60)  # Increased timeout to 60 seconds
            logger.info("TACACS+ server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server group: {str(e)}")

    @aetest.test
    def configure_command_authorization(self, device, custom):
        """Enable privilege level 15 command authorization"""
        try:
            authorization_config = [
                f"aaa authorization commands 15 default group {custom['tacacs_server_group']} local"
            ]
            device.configure(authorization_config, timeout=60)  # Increased timeout to 60 seconds
            logger.info("Command authorization configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure command authorization: {str(e)}")

    @aetest.test
    def execute_privilege_15_command(self, device):
        """Execute a privilege level 15 command and verify authorization"""
        try:
            # Execute a privilege level 15 command
            output = device.execute("show running-config", timeout=60)  # Increased timeout to 60 seconds
            if output:
                logger.info("Privilege level 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege level 15 command.")

            # Verify authorization logs
            logs = device.execute("show logging | include TACACS", timeout=60)  # Increased timeout to 60 seconds
            logger.info("Collected TACACS+ authorization logs:")
            logger.info(logs)

            if "Authorization" in logs or "AUTH" in logs:
                logger.info("Authorization is successful.")
            else:
                self.failed("Authorization logs not found.")
        except Exception as e:
            self.failed(f"Failed to execute commands or verify authorization: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device, custom):
        """Remove test configuration"""
        cleanup_cmds = [
            f"no tacacs server {custom['tacacs_server_name']}",
            f"no aaa group server tacacs+ {custom['tacacs_server_group']}",
            "no aaa authorization commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds, timeout=60)  # Increased timeout to 60 seconds
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
