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

            # Configure TACACS+ server groups
            server_group_config = [
                "aaa group server tacacs+ TLS_GROUP",
                " server name TLS1",
                " server name TLS2",
                "aaa group server tacacs+ NON_TLS_GROUP",
                " server name NON_TLS1",
                " server name NON_TLS2"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ servers and server groups configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ servers: {str(e)}")

    @aetest.test
    def configure_login_authentication(self, device):
        """Configure login authentication using the TACACS+ server groups"""
        try:
            # Configure login authentication
            login_auth = [
                "aaa authentication login default group TLS_GROUP group NON_TLS_GROUP local"
            ]
            device.configure(login_auth)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def enable_authorization(self, device):
        """Enable authorization with TACACS+ server groups"""
        try:
            # Configure authorization
            authorization_config = [
                "aaa authorization exec default group TLS_GROUP group NON_TLS_GROUP local",
                "aaa authorization commands 15 default group TLS_GROUP group NON_TLS_GROUP local"
            ]
            device.configure(authorization_config)
            logger.info("Authorization configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure authorization: {str(e)}")

    @aetest.test
    def perform_ssh_login_and_verify(self, device):
        """Perform SSH login and verify privilege level 15 commands"""
        try:
            # Simulate SSH login by executing a privilege level 15 command
            output = device.execute("show running-config")
            if output:
                logger.info("Privilege level 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege level 15 command.")
        except Exception as e:
            self.failed(f"Failed to perform SSH login or execute commands: {str(e)}")

    @aetest.test
    def verify_fallback_to_non_tls(self, device):
        """Verify the request is triggered to the Non-TLS server group when TLS servers are not responding"""
        try:
            # Simulate TLS server failure
            device.configure("no tacacs server TLS1")
            device.configure("no tacacs server TLS2")

            # Collect debug logs
            logs = device.execute("show logging | include TACACS")
            logger.info("Collected TACACS+ debug logs:")
            logger.info(logs)

            # Verify if the request is sent to the Non-TLS server group
            if "NON_TLS1" in logs or "NON_TLS2" in logs:
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
        cleanup_cmds = [
            "no tacacs server TLS1",
            "no tacacs server TLS2",
            "no tacacs server NON_TLS1",
            "no tacacs server NON_TLS2",
            "no aaa group server tacacs+ TLS_GROUP",
            "no aaa group server tacacs+ NON_TLS_GROUP",
            "no aaa authentication login default",
            "no aaa authorization exec default",
            "no aaa authorization commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
