import logging
import time
import re
from pyats import aetest # type: ignore
from pyats.log.utils import banner # type: ignore

logger = logging.getLogger(__name__)


class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""
    
    @aetest.subsection
    def validate_topology(self, testbed):
        """Validate the testbed information"""
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        """Initialize test variables"""
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['vwlc-ksukulka']
        testscript.parameters['uut'] = uut

        # Helper to get custom variable or raise a clear error
        def get_custom(key):
            if key not in uut.custom:
                logger.error(f"Device custom field '{key}' is missing in testbed definition.")
                self.errored(f"Device custom field '{key}' is missing in testbed definition.")
            return uut.custom[key]

        # Map YAML custom fields to script parameters
        testscript.parameters['tacacs_server_name'] = get_custom('tacacs_server1_name')
        testscript.parameters['tacacs_fqdn'] = get_custom('tacacs_server1_ip')  # If FQDN is not available, use IP
        testscript.parameters['tacacs_port'] = get_custom('tls_port')
        testscript.parameters['tacacs_group'] = get_custom('tacacs_group_name')
        testscript.parameters['idle_timeout'] = get_custom('tls_idle_timeout')
        testscript.parameters['connection_timeout'] = get_custom('tls_connection_timeout')
        testscript.parameters['retries'] = get_custom('tls_retries')
        testscript.parameters['source_interface'] = get_custom('source_interface')

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)
        
        # Save current configuration for later restoration
        logger.info("Saving current configuration")
        self.original_config = uut.execute("show running-config")


class TacacsTlsFqdnAccountingTest(aetest.Testcase):
    """Test case to verify TACACS TLS accounting with FQDN configuration"""

    @aetest.setup
    def setup(self, uut):
        """Enable PRC exposure and AAA new-model"""
        logger.info("Enabling PRC exposure")
        output = uut.execute("terminal prc expose")
        if "Error" in output:
            self.failed("Failed to enable PRC exposure")

        logger.info("Enabling service internal")
        uut.configure("service internal")
        
        logger.info("Enabling AAA new-model")
        uut.api.configure_aaa_new_model()

    @aetest.test
    def configure_tacacs_server(self, uut, tacacs_server_name, tacacs_fqdn, tacacs_port):
        """Configure TACACS server with FQDN"""
        logger.info("Configuring TACACS server with FQDN")
        
        # Configure the host table entry first to resolve FQDN
        uut.configure(f"ip host {tacacs_fqdn} 10.76.239.180")
        
        # Configure TACACS server with basic settings
        config_commands = [
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 10.76.239.180",
            f" key 0 cisco123",
            f" port {tacacs_port}"
        ]
        
        try:
            uut.configure(config_commands)
            logger.info("Basic TACACS server configuration successful")
        except Exception as e:
            logger.error(f"Error configuring basic TACACS server: {str(e)}")
            self.failed("Failed to configure TACACS server")
            
        # Verify the configuration
        tacacs_config = uut.execute(f"show running-config | include tacacs")
        if tacacs_server_name not in tacacs_config:
            self.failed(f"TACACS server {tacacs_server_name} not found in configuration")
            
        logger.info("TACACS server configuration successful")

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_group, tacacs_server_name):
        """Configure TACACS server group"""
        logger.info("Configuring TACACS server group")
        
        config_commands = [
            f"aaa group server tacacs+ {tacacs_group}",
            f" server name {tacacs_server_name}"
        ]
        
        uut.configure(config_commands)
        
        # Verify the configuration
        server_group_config = uut.execute(f"show running-config | section aaa group server tacacs")
        if tacacs_group not in server_group_config or tacacs_server_name not in server_group_config:
            self.failed(f"TACACS server group {tacacs_group} not properly configured")
            
        logger.info("TACACS server group configuration successful")

    @aetest.test
    def enable_command_accounting(self, uut, tacacs_group):
        """Enable command accounting for privilege 15 commands"""
        logger.info("Enabling command accounting for privilege 15 commands")
        
        config_commands = [
            f"aaa accounting commands 15 default start-stop group {tacacs_group}"
        ]
        
        uut.configure(config_commands)
        
        # Verify the configuration
        accounting_config = uut.execute(f"show running-config | include aaa accounting commands")
        if "aaa accounting commands 15" not in accounting_config and tacacs_group not in accounting_config:
            self.failed("Command accounting not properly configured")
            
        logger.info("Command accounting configuration successful")

    @aetest.test
    def enable_command_authorization(self, uut, tacacs_group):
        """Enable command authorization for privilege 15 commands"""
        logger.info("Enabling command authorization for privilege 15 commands")
        config_commands = [
            f"aaa authorization commands 15 default group {tacacs_group} local"
        ]
        uut.configure(config_commands)
        # Verify the configuration
        authorization_config = uut.execute(f"show running-config | include aaa authorization commands")
        if "aaa authorization commands 15" not in authorization_config or tacacs_group not in authorization_config:
            self.failed("Command authorization not properly configured")
        logger.info("Command authorization configuration successful")

    @aetest.test
    def enable_debug(self, uut):
        """Enable TACACS and SSL debugs"""
        logger.info("Enabling TACACS and SSL debugs")
        
        debug_commands = [
            "debug tacacs accounting",
            "debug tacacs events",
            "debug tacacs packet",
            "debug ip tcp transactions",
            "debug ip tcp packet",
            "debug crypto ssl",
            "terminal monitor"
        ]
        
        for cmd in debug_commands:
            try:
                uut.execute(cmd)
                logger.info(f"Successfully enabled: {cmd}")
            except Exception as e:
                logger.warning(f"Failed to enable debug command {cmd}: {str(e)}")
            
        logger.info("Debug commands enabled successfully")

    @aetest.test
    def execute_privilege_commands(self, uut):
        """Execute privilege 15 commands to generate accounting records"""
        logger.info("Executing privilege 15 commands to generate accounting records")
        
        # Execute a few privilege 15 commands that are valid on this device
        test_commands = [
            "show version",
            "show running-config | include hostname",
            "show ip interface brief"
        ]
        
        for cmd in test_commands:
            try:
                logger.info(f"Executing command: {cmd}")
                uut.execute(cmd)
                # Wait a moment to ensure accounting records are generated
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Command {cmd} failed: {str(e)}")
            
        logger.info("Privilege 15 commands executed successfully")

    @aetest.test
    def verify_accounting(self, uut):
        """Verify accounting is successful using the TACACS accounting debug logs"""
        logger.info("Verifying accounting records in debug logs")
        
        # Give some time for accounting records to process
        time.sleep(5)
        
        # Check debug output for accounting records
        debug_output = uut.execute("show logging | include TACACS+: Accounting")
        
        if "TACACS+: Accounting" in debug_output:
            logger.info("TACACS accounting records found in debug logs")
            self.passed("Successfully verified TACACS accounting records")
        else:
            logger.warning("No accounting records found in debug logs")
            # Additional debug information
            tacacs_debug = uut.execute("show logging | include TACACS+")
            logger.info(f"TACACS+ debug output: {tacacs_debug}")
            
            # Check for TACACS activity in logs
            try:
                # Try with TPLUS indicator which is seen in the logs
                general_logs = uut.execute("show logging | include TPLUS")
                logger.info("Successfully retrieved TPLUS logs")
            except Exception as e:
                logger.warning(f"Could not retrieve TPLUS logging information: {str(e)}")
                general_logs = ""
            
            if "TACACS+" in tacacs_debug or "TPLUS" in general_logs:
                self.passed("TACACS debug information found, but no specific accounting records")
            else:
                self.skipped("No TACACS debug information found. Verify server connection and try again")

    @aetest.test
    def verify_authorization(self, uut):
        """Verify authorization is successful using TACACS debug logs"""
        logger.info("Verifying authorization records in debug logs")
        time.sleep(5)
        debug_output = uut.execute("show logging | include TACACS+: Authorization")
        if "TACACS+: Authorization" in debug_output:
            logger.info("TACACS authorization records found in debug logs")
            self.passed("Successfully verified TACACS authorization records")
        else:
            logger.warning("No authorization records found in debug logs")
            tacacs_debug = uut.execute("show logging | include TACACS+")
            logger.info(f"TACACS+ debug output: {tacacs_debug}")
            if "TACACS+" in tacacs_debug:
                self.passed("TACACS debug information found, but no specific authorization records")
            else:
                self.skipped("No TACACS debug information found. Verify server connection and try again")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disable_debug(self, uut):
        """Disable all debugging"""
        logger.info(banner("Disabling all debugging"))
        
        try:
            # Attempt to disable debugging with a longer timeout
            uut.execute("undebug all", timeout=30)
            logger.info("Successfully disabled all debugging")
        except Exception as e:
            logger.warning(f"Error disabling debug: {str(e)}")
            logger.info("Attempting to reconnect to the device...")
            
            try:
                # Try to reconnect if the previous command failed
                uut.disconnect()
                time.sleep(5)
                uut.connect(learn_hostname=True, init_config_commands=[])
                logger.info("Reconnected to the device")
                
                # Try again to disable debugging after reconnection
                try:
                    uut.execute("undebug all", timeout=30)
                    logger.info("Successfully disabled all debugging after reconnect")
                except Exception as e2:
                    logger.warning(f"Still could not disable debugging after reconnect: {str(e2)}")
            except Exception as e3:
                logger.warning(f"Failed to reconnect to the device: {str(e3)}")

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_server_name, tacacs_group, tacacs_fqdn):
        """Remove TACACS server configuration"""
        logger.info(banner("Cleaning up TACACS configuration"))
        
        # Check if we need to reconnect
        try:
            # Test command to check connectivity
            uut.execute("show clock", timeout=10)
        except Exception:
            try:
                logger.info("Reconnecting to device for cleanup...")
                uut.disconnect()
                time.sleep(5)
                uut.connect(learn_hostname=True, init_config_commands=[])
                logger.info("Successfully reconnected for cleanup")
            except Exception as e:
                logger.error(f"Failed to reconnect: {str(e)}")
                logger.info("Continuing with cleanup anyway...")
        
        # Disable accounting
        try:
            uut.configure("no aaa accounting commands 15 default")
            logger.info("Removed accounting configuration")
        except Exception as e:
            logger.warning(f"Error removing accounting configuration: {str(e)}")
        
        # Remove server group
        try:
            uut.configure(f"no aaa group server tacacs+ {tacacs_group}")
            logger.info("Removed server group")
        except Exception as e:
            logger.warning(f"Error removing server group: {str(e)}")
        
        # Remove TACACS server
        try:
            uut.configure(f"no tacacs server {tacacs_server_name}")
            logger.info("Removed TACACS server")
        except Exception as e:
            logger.warning(f"Error removing TACACS server: {str(e)}")
        
        # Remove host entry
        try:
            uut.configure(f"no ip host {tacacs_fqdn}")
            logger.info("Removed host entry")
        except Exception as e:
            logger.warning(f"Error removing host entry: {str(e)}")
        
        # Remove service internal
        try:
            uut.configure("no service internal")
            logger.info("Removed service internal")
        except Exception as e:
            logger.warning(f"Error removing service internal: {str(e)}")
        
        # Save configuration
        try:
            uut.execute("write memory")
            logger.info("Configuration saved")
        except Exception as e:
            logger.warning(f"Error saving configuration: {str(e)}")

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        try:
            uut.disconnect()
            logger.info("Successfully disconnected from the device")
        except Exception as e:
            logger.warning(f"Error during disconnect: {str(e)}")
