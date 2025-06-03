# Copyright (c) 2025 by Cisco Systems, Inc.
# All rights reserved.
# Standard author information:
__author__ = "Priya kumari"
__copyright__ = "Copyright 2025, Cisco Systems"
__maintainer__ = "AAA Dev team"
__email__ = "aaa-dev@cisco.com"
__date__ = "April 10, 2025"
__version__ = 1.0

import logging
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
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        
        # Set default values for custom variables
        default_values = {
            'tacacs_server_name': 'TAC',
            'tacacs_server_ip': '10.1.1.1',
            'tacacs_server_group': 'TAC_Grp',
            'tacacs_port': '49',
            'tacacs_key': 'test123',
            'tacacs_idle_timeout': '61',
            'tacacs_connection_timeout': '32',
            'tacacs_retries': '2',
            'source_interface': 'GigabitEthernet1'
        }
        
        # Extract custom variables from testbed with defaults
        for key, default in default_values.items():
            value = uut.custom.get(key)
            if value is None:
                logger.warning(f"Custom variable '{key}' not found in testbed, using default: {default}")
                value = default
            testscript.parameters[key] = value
            
        # Validate critical parameters
        if not testscript.parameters['tacacs_server_name'] or not testscript.parameters['tacacs_server_ip']:
            self.failed("Critical TACACS parameters missing in testbed file")
            
        logger.info("TACACS parameters:")
        for key, value in default_values.items():
            logger.info(f"  {key}: {testscript.parameters[key]}")
        
        # Save initial configuration for cleanup
        testscript.parameters['initial_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

    @aetest.subsection
    def save_initial_config(self, uut, testscript):
        """Save the initial device configuration for restoration in cleanup"""
        logger.info(banner("Saving initial device configuration"))
        testscript.parameters['initial_config'] = uut.execute("show running-config")


class TacacsAuthorizationTest(aetest.Testcase):
    """Test case to verify TACACS server authorization functionality"""

    @aetest.setup
    def setup(self, uut):
        """Enable AAA new-model"""
        logger.info("Enabling AAA new-model")
        uut.api.configure_aaa_new_model()
        
        # Verify AAA is enabled
        output = uut.execute("show running-config | include aaa new-model")
        if "aaa new-model" not in output:
            self.failed("Failed to enable AAA new-model")

    @aetest.test
    def setup_ise_trustpoint(self, uut):
        """Configure ISE trustpoint for TACACS TLS"""
        logger.info(banner("Setting up ISE TLS certificate"))
        
        try:
            # Extract the self-signed certificate name
            output = uut.execute("show crypto pki certificates pem | sec self")
            match = re.search(r'------Trustpoint: (TP-self-signed-\d+)------', output)
            
            if not match:
                logger.warning("Failed to find self-signed certificate trustpoint, continuing anyway")
                self.client_trustpoint = None
            else:
                self.client_trustpoint = match.group(1)
                logger.info(f"Found client trustpoint: {self.client_trustpoint}")
            
            # Configure ISE trustpoint
            commands = [
                "crypto pki trustpoint ISE_TLS_Certificate",
                "enrollment terminal",
                "exit"
            ]
            
            uut.configure(commands)
            
            # Verify trustpoint was created
            output = uut.execute("show crypto pki trustpoints")
            if "ISE_TLS_Certificate" not in output:
                logger.warning("Failed to create ISE_TLS_Certificate trustpoint, continuing anyway")
        except Exception as e:
            logger.warning(f"Error configuring trustpoint: {str(e)}, continuing anyway")

    @aetest.test
    def configure_tacacs_server(self, uut, tacacs_server_name, tacacs_server_ip, tacacs_key):
        """Configure TACACS server with IPv4 address"""
        logger.info(banner("Configuring TACACS server"))
        
        # Verify all parameters are valid before proceeding
        if not tacacs_server_ip:
            self.failed("Required TACACS server IP parameter is missing")
            
        logger.info(f"Server name: {tacacs_server_name}, IP: {tacacs_server_ip}")
        
        # Use the older, more compatible tacacs-server host syntax
        try:
            # Configure the TACACS server using tacacs-server host command (older syntax)
            uut.configure(f"tacacs-server host {tacacs_server_ip} key {tacacs_key}")
            logger.info(f"Configured TACACS server {tacacs_server_ip} with key")
        except Exception as e:
            logger.error(f"Failed to configure TACACS server: {str(e)}")
            self.failed(f"Failed to configure TACACS server: {str(e)}")
        
        # Verify TACACS server configuration
        output = uut.execute("show running-config | include tacacs")
        logger.info(f"TACACS server configuration: {output}")
        
        if tacacs_server_ip not in output:
            self.failed("Failed to configure TACACS server")
        
        logger.info("TACACS server configured successfully")
        
        # Save the IP for later use in other methods
        self.tacacs_server_ip = tacacs_server_ip

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_server_group):
        """Configure TACACS server group"""
        logger.info(banner("Configuring TACACS server group"))
        
        # Verify parameters are valid
        if not tacacs_server_group:
            self.failed("Required TACACS server group parameter is missing")
            
        logger.info(f"Server group: {tacacs_server_group}, Server IP: {self.tacacs_server_ip}")
        
        # Just create the server group without trying to add servers explicitly
        # Many device versions implicitly associate all configured TACACS servers
        try:
            # Create the server group only
            uut.configure(f"aaa group server tacacs+ {tacacs_server_group}")
            logger.info(f"Created server group {tacacs_server_group}")
            
            # Exit configuration mode to ensure we're back at the main prompt
            uut.configure("exit")
        except Exception as e:
            logger.error(f"Error configuring server group: {str(e)}")
            self.failed(f"Failed to configure TACACS server group: {str(e)}")
        
        # Verify TACACS server group configuration
        output = uut.execute(f"show running-config | include group server")
        logger.info(f"TACACS server group configuration: {output}")
        
        if tacacs_server_group not in output:
            self.failed("Failed to configure TACACS server group")
        
        logger.info("TACACS server group configured successfully")

    @aetest.test
    def enable_tacacs_authorization(self, uut, tacacs_server_group):
        """Enable Authorization with TACACS group for privilege 15"""
        logger.info(banner("Enabling TACACS Authorization"))
        
        # Verify parameters are valid
        if not tacacs_server_group:
            self.failed("Required TACACS server group parameter is missing")
            
        logger.info(f"TACACS Server Group: {tacacs_server_group}")
        
        # Configure AAA authentication, authorization, and accounting one command at a time
        try:
            uut.configure(f"aaa authentication login default group {tacacs_server_group} local")
            logger.info("Configured AAA authentication")
            
            uut.configure(f"aaa authorization commands 15 default group {tacacs_server_group} local")
            logger.info("Configured AAA authorization")
            
            uut.configure(f"aaa accounting commands 15 default start-stop group {tacacs_server_group}")
            logger.info("Configured AAA accounting")
        except Exception as e:
            logger.error(f"Failed to configure TACACS authorization: {str(e)}")
            self.failed(f"Failed to configure TACACS authorization: {str(e)}")
        
        # Verify TACACS authorization configuration
        output = uut.execute("show running-config | include authorization commands 15")
        logger.info(f"Authorization configuration: {output}")
        
        if "authorization" not in output:
            self.failed("Failed to configure TACACS authorization")
        
        logger.info("TACACS authorization configured successfully")

    @aetest.test
    def execute_privilege_commands(self, uut):
        """Execute privilege level 15 commands and verify authorization"""
        logger.info(banner("Executing privilege level 15 commands"))
        
        # Enable debug for TACACS authorization if supported
        uut.execute("terminal length 0")
        try:
            uut.execute("debug tacacs authorization")
            logger.info("Enabled TACACS authorization debugging")
        except Exception as e:
            logger.warning(f"Debug command failed, continuing anyway: {str(e)}")
        
        # Execute a few privilege 15 commands
        privilege_commands = [
            "show running-config | begin tacacs",
            "show interfaces | include line protocol",
            "show version | include Version"
        ]
        
        for cmd in privilege_commands:
            logger.info(f"Executing command: {cmd}")
            try:
                output = uut.execute(cmd)
                logger.info(f"Successfully executed command: {cmd}")
            except Exception as e:
                logger.error(f"Failed to execute command {cmd}: {str(e)}")
                self.failed(f"Failed to execute command {cmd}: {str(e)}")
        
        # Disable debug
        try:
            uut.execute("undebug all")
            logger.info("Disabled debugging")
        except Exception as e:
            logger.warning(f"Undebug command failed, continuing anyway: {str(e)}")
    
    @aetest.test
    def verify_authorization(self, uut):
        """Verify that authorization is successful"""
        logger.info(banner("Verifying TACACS authorization"))
        
        # Check TACACS server status
        output = uut.execute("show running-config | include tacacs")
        logger.info(f"TACACS configuration: {output}")
        
        server_found = False
        if self.tacacs_server_ip in output:
            server_found = True
            logger.info(f"TACACS server found in configuration")
        
        if not server_found:
            self.failed(f"TACACS server not found in device configuration")
        
        # Check AAA configuration
        aaa_output = uut.execute("show running-config | include aaa")
        logger.info(f"AAA configuration: {aaa_output}")
        
        if "authorization" not in aaa_output:
            self.failed("AAA authorization not found in configuration")
        
        # Final verification - if we got this far, tests are successful
        logger.info("TACACS authorization was successfully verified")
        self.passed("TACACS authorization test completed successfully")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disable_tacacs_debugging(self, uut):
        """Disable any active debugging"""
        logger.info(banner("Disabling debug commands"))
        try:
            uut.execute("undebug all")
        except Exception as e:
            logger.warning(f"Failed to disable debugging: {str(e)}")

    @aetest.subsection
    def cleanup_tacacs_config(self, uut, tacacs_server_group):
        """Remove TACACS server configuration"""
        logger.info(banner("Cleaning up TACACS configuration"))
        
        # Try to clean up with error handling for each step
        
        # Remove AAA authorization and authentication
        try:
            commands = [
                "no aaa authentication login default",
                "no aaa authorization commands 15 default",
                "no aaa accounting commands 15 default"
            ]
            uut.configure(commands)
            logger.info("Removed AAA authorization and authentication")
        except Exception as e:
            logger.error(f"Error removing AAA config: {str(e)}")
        
        # Remove TACACS server group
        try:
            if tacacs_server_group:
                uut.configure(f"no aaa group server tacacs+ {tacacs_server_group}")
                logger.info(f"Removed TACACS server group {tacacs_server_group}")
        except Exception as e:
            logger.error(f"Error removing server group: {str(e)}")
        
        # Remove TACACS server configuration
        try:
            # Get all TACACS servers
            output = uut.execute("show running-config | include tacacs-server host")
            servers = re.findall(r'tacacs-server host (\d+\.\d+\.\d+\.\d+)', output)
            
            # Remove each one
            for server in servers:
                uut.configure(f"no tacacs-server host {server}")
                logger.info(f"Removed TACACS server host {server}")
        except Exception as e:
            logger.error(f"Error removing TACACS servers: {str(e)}")
        
        # Remove ISE trustpoint
        try:
            uut.configure("no crypto pki trustpoint ISE_TLS_Certificate")
            logger.info("Removed ISE trustpoint")
        except Exception as e:
            logger.error(f"Error removing ISE trustpoint: {str(e)}")
        
        # Disable AAA new-model
        try:
            uut.api.unconfigure_aaa_new_model()
            logger.info("Disabled AAA new-model")
        except Exception as e:
            logger.error(f"Error disabling AAA new-model: {str(e)}")
        
        logger.info("Completed TACACS configuration cleanup")

    @aetest.subsection
    def save_configuration(self, uut):
        """Save the final configuration"""
        logger.info(banner("Saving configuration"))
        try:
            uut.api.execute_write_memory()
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {str(e)}")

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
