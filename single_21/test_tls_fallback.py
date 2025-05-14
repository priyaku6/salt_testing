import logging
import paramiko
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
    def configure_login_authentication(self, device):
        """Configure login authentication using the TACACS+ server group"""
        try:
            login_auth_config = [
                "aaa authentication login default group TACACS_GROUP local"
            ]
            device.configure(login_auth_config)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def perform_ssh_login(self):
        """Perform an SSH login to the device and verify failure"""
        ssh_ip = "10.76.239.180"  # Replace with the actual device IP
        ssh_username = "invalid_user"  # Invalid username for testing
        ssh_password = "invalid_password"  # Invalid password for testing

        try:
            # Initialize SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            # Attempt SSH login
            logger.info(f"Attempting SSH login to {ssh_ip} with username '{ssh_username}'")
            ssh_client.connect(
                hostname=ssh_ip,
                username=ssh_username,
                password=ssh_password,
                timeout=10
            )
            self.failed("SSH login succeeded unexpectedly.")
        except paramiko.AuthenticationException:
            logger.info("SSH login failed as expected.")
        except Exception as e:
            self.failed(f"Failed to perform SSH login: {str(e)}")
        finally:
            ssh_client.close()

    @aetest.test
    def verify_request_not_triggered_to_non_tls(self, device):
        """Verify the request is not triggered to the Non-TLS server"""
        try:
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
            self.failed(f"Failed to verify request behavior: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server TLS_SERVER",
            "no tacacs server NonTLS_SERVER",
            "no aaa group server tacacs+ TACACS_GROUP",
            "no aaa authentication login default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
