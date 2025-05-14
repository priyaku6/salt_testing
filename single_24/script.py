import logging
from pyats import aetest
from pyats.log.utils import banner
from pyats.topology import loader

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
            "debug tacacs events",
            "debug tacacs authentication",
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
        """Configure TACACS+ servers and server groups"""
        try:
            # Retrieve TACACS+ configuration from the testbed
            tacacs_server_name = device.custom['tacacs_server_name']
            tacacs_server_group = device.custom['tacacs_server_group']
            tacacs_ip = device.custom['tacacs_ip']
            tls_port = device.custom['tls_port']

            # Configure TACACS+ server
            tacacs_config = [
                f"tacacs server {tacacs_server_name}",
                f" address ipv4 {tacacs_ip}",
                " key tacacs_key",
                " timeout 5",
                f" port {tls_port}",
                " tls"
            ]
            device.configure(tacacs_config)

            # Configure TACACS+ server group
            server_group_config = [
                f"aaa group server tacacs+ {tacacs_server_group}",
                f" server name {tacacs_server_name}"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ server and server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def configure_login_authentication(self, device):
        """Configure login authentication using the TACACS+ server group"""
        try:
            # Retrieve TACACS+ server group from the testbed
            tacacs_server_group = device.custom['tacacs_server_group']

            # Configure login authentication
            login_auth = [
                f"aaa authentication login default group {tacacs_server_group} local"
            ]
            device.configure(login_auth)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def perform_ssh_login(self, device):
        """Perform SSH login to the device"""
        try:
            # Simulate SSH login by executing a command
            output = device.execute("show version")
            if output:
                logger.info("SSH login successful.")
            else:
                self.failed("SSH login failed.")
        except Exception as e:
            self.failed(f"Failed to perform SSH login: {str(e)}")

    @aetest.test
    def verify_fallback_to_non_tls(self, device):
        """Verify the request is triggered to the Non-TLS server group when TLS servers are not responding"""
        try:
            # Simulate TLS server failure
            tacacs_server_name = device.custom['tacacs_server_name']
            device.configure(f"no tacacs server {tacacs_server_name}")

            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs:")
            logger.info(logs)

            # Verify if the request is sent to the Non-TLS server group
            if "NON_TLS" in logs:
                logger.info("Request is correctly triggered to the Non-TLS server group.")
            else:
                self.failed("Request is not triggered to the Non-TLS server group when TLS servers are not responding.")
        except Exception as e:
            self.failed(f"Failed to verify fallback behavior: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        try:
            # Retrieve TACACS+ configuration from the testbed
            tacacs_server_name = device.custom['tacacs_server_name']
            tacacs_server_group = device.custom['tacacs_server_group']

            # Cleanup commands
            cleanup_cmds = [
                f"no tacacs server {tacacs_server_name}",
                f"no aaa group server tacacs+ {tacacs_server_group}",
                "no aaa authentication login default",
                "no debug all"
            ]
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
