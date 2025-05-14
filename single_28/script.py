import logging
from pyats import aetest
from pyats.log.utils import banner
from time import sleep

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device with retry logic"""
        retries = 3
        for attempt in range(retries):
            try:
                self.device = testbed.devices['vwlc-ksukulka']  # Replace with the correct device name
                self.device.connect(via='ssh', timeout=60)  # Increased timeout to 60 seconds
                self.parent.parameters['device'] = self.device  # Pass the device to test cases
                logger.info(f"Connected to device: {self.device.name}")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < retries - 1:
                    sleep(5)  # Wait before retrying
                else:
                    self.failed(f"Failed to connect to device after {retries} attempts.")

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs with retry logic"""
        debug_commands = [
            "terminal monitor",
            "debug aaa authentication",
            "debug aaa authorization",
            "debug tacacs events",
            "debug tacacs authentication",
            "debug ssl errors"
        ]
        for cmd in debug_commands:
            retries = 3
            for attempt in range(retries):
                try:
                    device.execute(cmd, timeout=60)  # Increased timeout to 60 seconds
                    break
                except Exception as e:
                    logger.warning(f"Failed to execute debug command '{cmd}' on attempt {attempt + 1}: {str(e)}")
                    if attempt < retries - 1:
                        sleep(5)  # Wait before retrying
                    else:
                        logger.error(f"Failed to execute debug command '{cmd}' after {retries} attempts.")
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
            device.configure(nontls_config, timeout=60)  # Increased timeout to 60 seconds

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
            device.configure(tls_config, timeout=60)  # Increased timeout to 60 seconds

            # Configure TACACS+ server groups
            server_group_config = [
                "aaa group server tacacs+ NON_TLS_GROUP",
                " server name NON_TLS1",
                " server name NON_TLS2",
                "aaa group server tacacs+ TLS_GROUP",
                " server name TLS1",
                " server name TLS2"
            ]
            device.configure(server_group_config, timeout=60)  # Increased timeout to 60 seconds

            logger.info("TACACS+ servers and server groups configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ servers: {str(e)}")

    @aetest.test
    def configure_authorization(self, device):
        """Enable authorization for privilege level 15 commands"""
        try:
            # Configure authorization
            authorization_config = [
                "aaa authorization commands 15 default group NON_TLS_GROUP group TLS_GROUP local"
            ]
            device.configure(authorization_config, timeout=60)  # Increased timeout to 60 seconds
            logger.info("Authorization configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure authorization: {str(e)}")

    @aetest.test
    def execute_privilege_15_commands(self, device):
        """Execute privilege level 15 commands and verify authorization"""
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

    @aetest.test
    def verify_fallback_to_tls(self, device):
        """Verify the request is triggered to the TLS server group when Non-TLS servers are not responding"""
        try:
            # Simulate Non-TLS server failure
            device.configure("no tacacs server NON_TLS1", timeout=60)  # Increased timeout to 60 seconds
            device.configure("no tacacs server NON_TLS2", timeout=60)  # Increased timeout to 60 seconds

            # Execute a privilege level 15 command
            output = device.execute("show running-config", timeout=60)  # Increased timeout to 60 seconds
            if output:
                logger.info("Privilege level 15 command executed successfully.")
            else:
                self.failed("Failed to execute privilege level 15 command.")

            # Collect debug logs
            logs = device.execute("show logging | include TACACS", timeout=60)  # Increased timeout to 60 seconds
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
            "no aaa authorization commands 15 default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds, timeout=60)  # Increased timeout to 60 seconds
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
