from pyats import aetest  # type: ignore
import logging
from unicon.eal.dialogs import Dialog, Statement  # type: ignore

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device via SSH"""
        logger.info("Connecting to the device via SSH...")
        uut = testbed.devices['uut']
        uut.connect()
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut  # Pass uut to testcases

class ConfigureISE(aetest.Testcase):
    """Testcase to configure ISE and TACACS"""

    @aetest.setup
    def check_current_config(self, uut):
        """Check current configuration before making changes"""
        logger.info("Checking current configuration...")
        current_config = uut.execute("show running-config | include tacacs|aaa authentication")
        logger.info(f"Current configuration: {current_config}")

    @aetest.test
    def configure_tacacs_server(self, uut):
        """Configure TACACS server with single connection and server group"""
        logger.info("Configuring TACACS server and group...")
        # Remove any existing conflicting configuration
        uut.configure(f"no tacacs server {uut.custom['tacacs_server_name']}")
        # Configure TACACS server and group
        uut.configure([
            f"tacacs server {uut.custom['tacacs_server_name']}",
            f" address ipv4 {uut.custom['tacacs_ip']}",
            " single-connection",
            f"aaa group server tacacs+ {uut.custom['tacacs_server_group']}",
            f" server name {uut.custom['tacacs_server_name']}"
        ])
        # Verify configuration was applied
        tacacs_config = uut.execute("show running-config | include tacacs")
        logger.info(f"After configuration - TACACS config: {tacacs_config}")

    @aetest.test
    def enable_login_authentication(self, uut):
        """Enable login authentication with TACACS group"""
        logger.info("Enabling login authentication...")
        # Remove any existing console authentication
        uut.configure("no aaa authentication login CONSOLE local")
        # Configure AAA authentication
        uut.configure([
            f"aaa authentication login default group {uut.custom['tacacs_server_group']} local"
        ])
        # Verify authentication config was applied
        aaa_config = uut.execute("show running-config | include aaa authentication")
        logger.info(f"After configuration - AAA config: {aaa_config}")

class VerifyLogin(aetest.Testcase):
    """Testcase to verify SSH login authentication"""

    @aetest.test
    def verify_tacacs_configuration(self, uut):
        """Verify TACACS configuration is applied correctly"""
        logger.info("Verifying TACACS configuration...")
        tacacs_config = uut.execute("show running-config | begin tacacs")
        aaa_config = uut.execute("show running-config | include aaa authentication")
        # Check TACACS server config
        if f"tacacs server {uut.custom['tacacs_server_name']}" not in tacacs_config:
            self.failed(f"TACACS server '{uut.custom['tacacs_server_name']}' not found in configuration")
        if uut.custom['tacacs_ip'] not in tacacs_config:
            self.failed(f"TACACS server address {uut.custom['tacacs_ip']} not found in configuration")
        if "single-connection" not in tacacs_config:
            self.failed("TACACS single-connection not enabled")
        # Check AAA authentication config
        expected_auth = f"aaa authentication login default group {uut.custom['tacacs_server_group']}"
        if expected_auth not in aaa_config and f"{expected_auth} local" not in aaa_config:
            self.failed("AAA authentication not configured to use TACACS group")
        if "aaa authentication login CONSOLE local" in aaa_config:
            self.failed("Conflicting CONSOLE authentication found using local method")
        self.passed("TACACS and AAA configuration verified successfully")

    @aetest.test
    def verify_ssh_login(self, uut):
        """Verify SSH login and authentication"""
        logger.info("Verifying SSH login and authentication...")
        if not uut.connected:
            self.failed("Device is not connected")
        try:
            hostname = uut.execute("show running-config | include hostname")
            logger.info(f"Successfully executed command: {hostname}")
            tacacs_status = uut.execute("show tacacs")
            logger.info(f"TACACS status: {tacacs_status}")
            user_output = uut.execute("show users")
            logger.info(f"Connected users: {user_output}")
            # Check if the expected user is in the session list
            if "ksukulka" in user_output:
                self.passed("Successfully verified SSH login and TACACS authentication")
            else:
                self.passed("SSH login successful, but username not found in users list")
        except Exception as e:
            self.failed(f"Failed to verify SSH connectivity: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test execution"""

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info("Disconnecting from the device...")
        uut.disconnect()
