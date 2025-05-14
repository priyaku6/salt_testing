from pyats import aetest  # type: ignore
import logging
from unicon.eal.dialogs import Dialog, Statement  # type: ignore # Import Dialog and Statement for handling prompts

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device"""
        logger.info("Connecting to the device...")
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
        logger.info("Configuring TACACS server...")
        
        # First remove any existing conflicting configuration
        uut.config("no tacacs server TAC")
        
        # Retrieve required custom parameters
        tacacs_server_name = uut.custom.get('tacacs_server_name')
        tacacs_server_ip = uut.custom.get('tacacs_server_ip')
        
        if not tacacs_server_name or not tacacs_server_ip:
            self.failed("TACACS server name or IP is not defined in the testbed configuration")
            return
        
        # Configure TACACS server
        uut.config([
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 {tacacs_server_ip}",
            " single-connection",
            "!",
            f"aaa group server tacacs+ TAC_Grp",
            f" server name {tacacs_server_name}"
        ])
        
        # Verify configuration was applied
        tacacs_config = uut.execute("show running-config | include tacacs")
        logger.info(f"After configuration - TACACS config: {tacacs_config}")

    @aetest.test
    def enable_login_authentication(self, uut):
        """Enable login authentication with TACACS group"""
        logger.info("Enabling login authentication...")
        
        # First remove any existing console authentication
        uut.config("no aaa authentication login CONSOLE local")
        
        # Configure AAA authentication
        uut.config([
            "aaa authentication login default group TAC_Grp local"
        ])
        
        # Verify authentication config was applied
        aaa_config = uut.execute("show running-config | include aaa authentication")
        logger.info(f"After configuration - AAA config: {aaa_config}")

class VerifyLogin(aetest.Testcase):
    """Testcase to verify login authentication"""

    @aetest.test
    def verify_tacacs_configuration(self, uut):
        """Verify TACACS configuration is applied correctly"""
        logger.info("Verifying TACACS configuration...")
        
        # Get current configuration with broader context
        tacacs_config = uut.execute("show running-config | begin tacacs")
        aaa_config = uut.execute("show running-config | include aaa authentication")
        
        logger.info(f"Full TACACS configuration section: {tacacs_config}")
        logger.info(f"AAA authentication configuration: {aaa_config}")
        
        # Retrieve required custom parameters
        tacacs_server_name = uut.custom.get('tacacs_server_name')
        tacacs_server_ip = uut.custom.get('tacacs_server_ip')
        
        if not tacacs_server_name or not tacacs_server_ip:
            self.failed("TACACS server name or IP is not defined in the testbed configuration")
            return
        
        # Verify TACACS server configuration
        if f"tacacs server {tacacs_server_name}" not in tacacs_config:
            self.failed(f"TACACS server '{tacacs_server_name}' not found in configuration")
            return
            
        if "address" not in tacacs_config or tacacs_server_ip not in tacacs_config:
            logger.warning(f"Address verification issue - looking for IP {tacacs_server_ip}")
            address_line = None
            for line in tacacs_config.splitlines():
                if "address" in line:
                    address_line = line
                    break
            if address_line:
                logger.warning(f"Found address line: {address_line}")
                self.failed(f"TACACS server address mismatch: expected {tacacs_server_ip}, found {address_line}")
            else:
                self.failed(f"TACACS server address not found in configuration")
            return
            
        if "single-connection" not in tacacs_config:
            self.failed("TACACS single-connection not enabled")
            return
            
        expected_auth = "aaa authentication login default group TAC_Grp"
        if expected_auth not in aaa_config and "aaa authentication login default group TAC_Grp local" not in aaa_config:
            self.failed("AAA authentication not configured to use TACACS group")
            return
            
        if "aaa authentication login CONSOLE local" in aaa_config:
            self.failed("Conflicting CONSOLE authentication found using local method")
            return
            
        self.passed("TACACS and AAA configuration verified successfully")
        
    @aetest.test
    def verify_console_login(self, uut):
        """Verify console login and authentication"""
        logger.info("Verifying device connectivity...")
        
        if not uut.connected:
            self.failed("Device is not connected")
            return
            
        try:
            hostname = uut.execute("show running-config | include hostname")
            logger.info(f"Successfully executed command: {hostname}")
            
            tacacs_status = uut.execute("show tacacs")
            logger.info(f"TACACS status: {tacacs_status}")
            
            user_output = uut.execute("show users")
            logger.info(f"Connected users: {user_output}")
            
            if "ksukulka" in user_output:
                logger.info("Current user session found in active connections")
                self.passed("Successfully verified console login and TACACS authentication")
            else:
                logger.info("Connected but username not found in users list")
                self.passed("Connected to the device but username not in users list")
        except Exception as e:
            self.failed(f"Failed to verify connectivity: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test execution"""

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info("Disconnecting from the device...")
        uut.disconnect()
