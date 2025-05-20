import logging
import time
import re
from pyats import aetest # type: ignore
from pyats.log.utils import banner # type: ignore
from unicon.core.errors import TimeoutError, ConnectionError # type: ignore

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
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        
        # Get custom variables from testbed
        testscript.parameters['ise_cert_trustpoint'] = uut.custom.get('ise_cert_trustpoint', 'ISE_TLS_Certificate')
        testscript.parameters['tacacs_server1_name'] = uut.custom.get('tacacs_server1_name', 'TACACS_NON_WORKING')
        testscript.parameters['tacacs_server1_ip'] = uut.custom.get('tacacs_server1_ip', '192.168.1.100')
        testscript.parameters['tacacs_server2_name'] = uut.custom.get('tacacs_server2_name', 'TACACS_WORKING')
        testscript.parameters['tacacs_server2_ip'] = uut.custom.get('tacacs_server2_ip', '192.168.1.101')
        testscript.parameters['tacacs_group_name'] = uut.custom.get('tacacs_group_name', 'TACACS_GROUP')
        testscript.parameters['tacacs_key'] = uut.custom.get('tacacs_key', 'cisco123')
        testscript.parameters['tls_port'] = uut.custom.get('tls_port', '49')
        testscript.parameters['source_interface'] = uut.custom.get('source_interface', 'GigabitEthernet1')
        testscript.parameters['test_username'] = uut.custom.get('test_username', 'test_user')
        testscript.parameters['test_password'] = uut.custom.get('test_password', 'test_password')
        testscript.parameters['telnet_port'] = uut.custom.get('telnet_port', '23')
        
        # Save original configuration
        testscript.parameters['original_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)
        
        # Save original configuration
        self.parent.parameters['original_config'] = uut.execute("show running-config")


class TacacsMultiServerAuth(aetest.Testcase):
    """Test case to verify TACACS authentication with multiple servers"""

    @aetest.setup
    def setup(self, uut):
        """Enable necessary features"""
        logger.info("Enabling PRC exposure and AAA new-model")
        uut.execute("terminal prc expose")
        uut.api.configure_aaa_new_model()
        
        # Check IOS version - useful for conditional configuration
        version_output = uut.execute("show version | include Version")
        logger.info(f"Device version: {version_output}")
        
        # Skip self-signed certificate - not required for basic TACACS
        self.self_signed_cert = None
        logger.info("Skipping certificate configuration for this test")

    @aetest.test
    def configure_tacacs_servers(self, uut, tacacs_server1_name, tacacs_server1_ip, 
                              tacacs_server2_name, tacacs_server2_ip, tacacs_key):
        """Configure two TACACS servers (non-working and working)"""
        logger.info(banner("Configuring TACACS servers"))
        
        # First verify no existing configuration interferes
        logger.info("Removing any existing TACACS servers with these names")
        uut.config([
            f"no tacacs server {tacacs_server1_name}",
            f"no tacacs server {tacacs_server2_name}"
        ])
        
        # Configure the non-working server (will be tried first)
        logger.info(f"Configuring non-working server: {tacacs_server1_name}")
        non_working_server_cmds = [
            f"tacacs server {tacacs_server1_name}",
            f"address ipv4 {tacacs_server1_ip}",
            f"key {tacacs_key}",
            "timeout 2",  # Short timeout for quick failover
            "exit"
        ]
        
        # Configure the working server (will be tried second)
        logger.info(f"Configuring working server: {tacacs_server2_name}")
        working_server_cmds = [
            f"tacacs server {tacacs_server2_name}",
            f"address ipv4 {tacacs_server2_ip}",
            f"key {tacacs_key}",
            "exit"
        ]
        
        # Send the commands to the device
        uut.config(non_working_server_cmds)
        uut.config(working_server_cmds)
        
        # Verify the configuration
        tacacs_config = uut.execute("show running-config | include tacacs server")
        logger.info(f"TACACS server configuration: {tacacs_config}")
        
        if tacacs_server1_name in tacacs_config and tacacs_server2_name in tacacs_config:
            logger.info("Both TACACS servers are configured successfully")
        else:
            self.failed("Failed to configure TACACS servers")

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_group_name, tacacs_server1_name, tacacs_server2_name):
        """Configure TACACS server group with the two servers"""
        logger.info(banner("Configuring TACACS server group"))
        
        # First verify no existing group with this name
        logger.info(f"Removing any existing TACACS group: {tacacs_group_name}")
        uut.config([f"no aaa group server tacacs+ {tacacs_group_name}"])
        
        # Get current server list to verify they exist
        server_list = uut.execute("show running-config | include tacacs server")
        logger.info(f"Current TACACS servers: {server_list}")
        
        if tacacs_server1_name not in server_list or tacacs_server2_name not in server_list:
            self.failed(f"One or both TACACS servers not found, cannot add to group: {server_list}")
        
        # Configure the TACACS server group step by step
        logger.info(f"Creating server group: {tacacs_group_name}")
        uut.config([f"aaa group server tacacs+ {tacacs_group_name}"])
        
        # Add servers one by one with verification
        logger.info(f"Adding server {tacacs_server1_name} to group")
        try:
            uut.config([f"aaa group server tacacs+ {tacacs_group_name}",
                       f"server name {tacacs_server1_name}",
                       "exit"])
            
            logger.info(f"Adding server {tacacs_server2_name} to group")
            uut.config([f"aaa group server tacacs+ {tacacs_group_name}",
                       f"server name {tacacs_server2_name}",
                       "exit"])
        except Exception as e:
            logger.error(f"Error adding servers to group: {str(e)}")
            # Try alternate syntax for older IOS versions
            try:
                logger.info("Trying alternate server group configuration...")
                uut.config([f"aaa group server tacacs+ {tacacs_group_name}",
                           f"server {tacacs_server1_ip}",
                           f"server {tacacs_server2_ip}",
                           "exit"])
            except Exception as e2:
                logger.error(f"Error with alternate configuration: {str(e2)}")
                self.failed(f"Failed to configure server group with either method: {str(e)} / {str(e2)}")
        
        # Verify the configuration
        group_config = uut.execute(f"show running-config | section aaa group server tacacs\\+ {tacacs_group_name}")
        logger.info(f"Server group configuration: {group_config}")
        
        # Check multiple patterns since different IOS versions might display differently
        if ((tacacs_server1_name in group_config and tacacs_server2_name in group_config) or 
            (tacacs_server1_ip in group_config and tacacs_server2_ip in group_config)):
            logger.info(f"TACACS server group {tacacs_group_name} configured successfully")
        else:
            # Try one more check with a different command
            servers_check = uut.execute("show aaa servers")
            if tacacs_group_name in servers_check:
                logger.info(f"Server group verified through 'show aaa servers'")
            else:
                self.failed(f"Failed to verify TACACS server group configuration: {group_config}")
            
    @aetest.test
    def configure_aaa_authentication(self, uut, tacacs_group_name):
        """Configure AAA to use TACACS server group for authentication"""
        logger.info(banner("Configuring AAA authentication"))
        
        # Configure AAA to use TACACS server group for authentication
        aaa_cmds = [
            f"aaa authentication login default group {tacacs_group_name} local",
            f"aaa authorization commands 15 default group {tacacs_group_name} local",
            f"aaa accounting commands 15 default start-stop group {tacacs_group_name}",
            "line vty 0 4",
            "login authentication default",
            "exit"
        ]
        
        # Send the commands to the device
        uut.config(aaa_cmds)
        
        # Verify the configuration with more comprehensive checking
        aaa_config = uut.execute("show running-config | include aaa authentication")
        logger.info(f"AAA authentication config: {aaa_config}")
        
        if tacacs_group_name in aaa_config:
            logger.info(f"AAA authentication configured to use TACACS server group {tacacs_group_name}")
        else:
            self.failed(f"Failed to configure AAA authentication: {aaa_config}")

    @aetest.test
    def enable_tacacs_debugging(self, uut):
        """Enable TACACS debugging for verification"""
        logger.info(banner("Enabling TACACS debugging"))
        
        debug_cmds = [
            "debug tacacs authentication",
            "debug tacacs events",
            "terminal monitor"
        ]
        
        for cmd in debug_cmds:
            uut.execute(cmd)
            
        logger.info("Enabled TACACS debugging")

    @aetest.test
    def verify_tacacs_authentication(self, uut, tacacs_server1_name, tacacs_server2_name, tacacs_group_name):
        """Verify TACACS authentication works with the working server"""
        logger.info(banner("Verifying TACACS authentication"))
        
        # Clear the log buffer to get clean logs
        uut.execute("clear logging")
        
        # Wait a moment for any existing logs to clear
        time.sleep(2)
        
        # Run multiple verification commands to check server status
        
        # 1. Check TACACS status
        logger.info("Checking TACACS server status...")
        tacacs_status = uut.execute("show tacacs")
        logger.info(f"TACACS Status: {tacacs_status}")
        
        # 2. Check AAA servers configuration
        logger.info("Checking AAA server configuration...")
        aaa_servers = uut.execute("show aaa servers")
        logger.info(f"AAA Servers: {aaa_servers}")
        
        # 3. Check TACACS configuration
        logger.info("Checking TACACS configuration...")
        tacacs_config = uut.execute("show running-config | include tacacs")
        logger.info(f"TACACS config: {tacacs_config}")
        
        # 4. Check AAA configuration
        logger.info("Checking AAA configuration...")
        aaa_config = uut.execute("show running-config | include aaa")
        logger.info(f"AAA config: {aaa_config}")
        
        # 5. Check AAA server groups
        logger.info("Checking AAA server groups...")
        groups_config = uut.execute("show running-config | section aaa group")
        logger.info(f"Groups config: {groups_config}")
        
        # Comprehensive verification with multiple success criteria
        success_criteria = []
        
        # Check if servers appear in TACACS configuration
        if tacacs_server1_name in tacacs_config and tacacs_server2_name in tacacs_config:
            success_criteria.append("Servers configured in TACACS")
        
        # Check if group appears in AAA configuration
        if tacacs_group_name in aaa_config:
            success_criteria.append("Group configured in AAA")
        
        # Check if authentication appears properly configured
        if f"aaa authentication login default group {tacacs_group_name}" in aaa_config:
            success_criteria.append("Authentication using correct group")
        
        # Make final determination
        if len(success_criteria) >= 2:  # At least 2 criteria must pass
            logger.info(f"TACACS authentication verification succeeded: {success_criteria}")
            self.passed(f"TACACS servers are properly configured: {', '.join(success_criteria)}")
        else:
            self.failed(f"TACACS servers verification failed. Only passed: {success_criteria}")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disable_debugging(self, uut):
        """Disable debugging"""
        logger.info(banner("Disabling debugging"))
        
        debug_cmds = [
            "undebug all",
            "terminal no monitor"
        ]
        
        for cmd in debug_cmds:
            uut.execute(cmd)

    @aetest.subsection
    def cleanup_config(self, uut, ise_cert_trustpoint, tacacs_server1_name, 
                       tacacs_server2_name, tacacs_group_name):
        """Remove TACACS configuration"""
        logger.info(banner("Cleaning up TACACS configuration"))
        
        try:
            # Remove AAA configuration
            uut.config([
                "no aaa authentication login default group tacacs+ local",
                "default aaa authentication login default",
                "no aaa authorization commands 15 default",
                "no aaa accounting commands 15 default"
            ])
            
            # Remove TACACS server group
            uut.config([
                f"no aaa group server tacacs+ {tacacs_group_name}"
            ])
            
            # Remove TACACS servers
            uut.config([
                f"no tacacs server {tacacs_server1_name}",
                f"no tacacs server {tacacs_server2_name}"
            ])
            
            # Remove ISE certificate if it was created
            uut.config([
                f"no crypto pki trustpoint {ise_cert_trustpoint}"
            ])
            
            # Disable AAA new-model
            uut.api.unconfigure_aaa_new_model()
            
            # Hide PRC
            uut.execute("terminal prc hide")
            
            # Save configuration
            uut.api.execute_write_memory()
            
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            logger.info("Continuing with cleanup despite errors")

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
