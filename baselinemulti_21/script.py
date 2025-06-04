# Copyright (c) 2024 by Cisco Systems, Inc.
# All rights reserved.

__author__ = "Priya kumari"
__copyright__ = "Copyright 2024, Cisco Systems"
__maintainer__ = "AAA Dev team"
__email__ = "aaa-dev@cisco.com"
__date__ = "April 11, 2025"
__version__ = 1.0

import logging
import re
import time
from pyats import aetest # type: ignore
from pyats.log.utils import banner # type: ignore

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for TACACS accounting test"""
    
    @aetest.subsection
    def validate_topology(self, testbed):
        """Validate the testbed information"""
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        """Initialize test variables from testbed"""
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        
        # Get custom variables from testbed
        testscript.parameters['tacacs_server_name'] = uut.custom.get('tacacs_server_name', 'TAC')
        testscript.parameters['tacacs_server_ip'] = uut.custom.get('tacacs_server_ip', '10.1.1.1')
        testscript.parameters['tacacs_port'] = uut.custom.get('tacacs_port', '49')
        testscript.parameters['tacacs_group_name'] = uut.custom.get('tacacs_group_name', 'TAC_Grp')
        testscript.parameters['source_interface'] = uut.custom.get('source_interface', 'GigabitEthernet1')
        testscript.parameters['privilege_level'] = uut.custom.get('privilege_level', '15')
        
        # Store initial configuration for cleanup
        testscript.parameters['initial_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info(f"Successfully connected to device {uut.name}")

    @aetest.subsection
    def backup_initial_configuration(self, uut, testscript):
        """Backup the initial configuration for restoring during cleanup"""
        logger.info(banner("Backing up initial configuration"))
        testscript.parameters['initial_config'] = uut.execute("show running-config")
        

class TacacsAccountingTest(aetest.Testcase):
    """Test case to verify TACACS accounting functionality"""

    @aetest.setup
    def setup(self, uut):
        """Enable required services for testing"""
        logger.info(banner("Setting up for TACACS accounting test"))
        
        # Enable service internal for debug commands
        logger.info("Enabling service internal")
        uut.configure("service internal")
        
        # Enable AAA new-model
        logger.info("Enabling AAA new-model")
        uut.api.configure_aaa_new_model()
        
        # Disable existing debugging (if any)
        logger.info("Disabling existing debug sessions")
        uut.execute("undebug all")

    @aetest.test
    def configure_tacacs_server(self, uut, tacacs_server_name, tacacs_server_ip, tacacs_port):
        """Configure TACACS server (without TLS)"""
        logger.info(banner("Configuring TACACS server"))
        
        # Configure TACACS server without TLS for simplicity
        commands = [
            f"tacacs server {tacacs_server_name}",
            " single-connection",
            f" address ipv4 {tacacs_server_ip}",
            f" key testing123",  # Simple shared key for testing
            " exit"  # Add explicit exit to ensure command mode returns properly
        ]
        
        result = uut.configure(commands)
        logger.info(f"TACACS server configuration result: {result}")
        
        # Verify TACACS server configuration
        tacacs_config = uut.execute("show running-config | section tacacs server")
        logger.info(f"TACACS server configuration: {tacacs_config}")
        
        if tacacs_server_name in tacacs_config:
            logger.info("TACACS server successfully configured")
        else:
            self.failed("TACACS server configuration failed or incomplete")

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_server_name, tacacs_group_name):
        """Configure TACACS server group"""
        logger.info(banner("Configuring TACACS server group"))
        
        # First check if the group already exists and remove it if necessary
        current_config = uut.execute("show running-config | section aaa group server")
        if tacacs_group_name in current_config:
            logger.info(f"Removing existing group {tacacs_group_name}")
            uut.configure(f"no aaa group server tacacs+ {tacacs_group_name}")
        
        # Now configure the server group with explicit exit
        commands = [
            f"aaa group server tacacs+ {tacacs_group_name}",
            f" server name {tacacs_server_name}",
            " exit"  # Add explicit exit to ensure command mode returns properly
        ]
        
        result = uut.configure(commands)
        logger.info(f"TACACS server group configuration result: {result}")
        
        # Small delay to ensure configuration is applied
        time.sleep(2)
        
        # Check full AAA configuration to see what's actually configured
        full_aaa_config = uut.execute("show running-config | section aaa")
        logger.info(f"Full AAA configuration: {full_aaa_config}")
        
        # More focused check for the specific group
        group_config = uut.execute(f"show running-config | section aaa group")
        logger.info(f"TACACS group config: {group_config}")
        
        # Now verify based on what we can see in the config
        if f"aaa group server tacacs+ {tacacs_group_name}" in full_aaa_config or tacacs_group_name in group_config:
            logger.info("TACACS server group successfully configured")
        else:
            # Try one more time with simpler verification
            simple_check = uut.execute(f"show running-config | include group")
            if tacacs_group_name in simple_check:
                logger.info("TACACS server group found with simpler verification")
            else:
                self.failed("TACACS server group configuration failed or incomplete")

    @aetest.test
    def configure_authentication(self, uut, tacacs_group_name):
        """Configure authentication using TACACS group"""
        logger.info(banner("Configuring authentication"))
        
        # First check and remove any existing default authentication
        logger.info("Checking for existing authentication configuration")
        existing_auth = uut.execute("show running-config | include aaa authentication login default")
        if existing_auth:
            logger.info("Removing existing default authentication")
            uut.configure("no aaa authentication login default")
        
        # Configure authentication with quotes around the command to handle spaces properly
        commands = [
            f"aaa authentication login default group {tacacs_group_name} local"
        ]
        
        result = uut.configure(commands)
        logger.info(f"Authentication configuration result: {result}")
        
        # Wait for configuration to be applied
        time.sleep(2)
        
        # Verify authentication configuration - try multiple approaches
        auth_config = uut.execute("show running-config | include authentication")
        logger.info(f"Authentication config: {auth_config}")
        
        # Check more broadly in case the include filter is too strict
        if tacacs_group_name in auth_config:
            logger.info("Authentication successfully configured")
        else:
            # Try checking the full AAA config section as backup
            all_aaa = uut.execute("show running-config | section aaa")
            logger.info(f"Full AAA configuration: {all_aaa}")
            
            if "aaa authentication login default" in all_aaa and tacacs_group_name in all_aaa:
                logger.info("Authentication found in full AAA section")
            else:
                # One more try - directly check if the config is there by parsing the running config
                full_config = uut.execute("show running-config")
                if f"aaa authentication login default group {tacacs_group_name}" in full_config:
                    logger.info("Authentication found in full running config")
                else:
                    self.failed("Authentication configuration failed or incomplete")

    @aetest.test
    def enable_accounting(self, uut, tacacs_group_name, privilege_level):
        """Enable accounting for privilege 15 commands with TACACS group"""
        logger.info(banner("Enabling accounting for privilege commands"))
        
        # First check and remove any existing accounting configuration
        logger.info("Checking for existing accounting configuration")
        existing_acct = uut.execute(f"show running-config | include aaa accounting commands {privilege_level}")
        if existing_acct:
            logger.info("Removing existing accounting configuration")
            uut.configure(f"no aaa accounting commands {privilege_level} default")
        
        commands = [
            f"aaa accounting commands {privilege_level} default start-stop group {tacacs_group_name}"
        ]
        
        result = uut.configure(commands)
        logger.info(f"Accounting configuration result: {result}")
        
        # Wait for configuration to be applied
        time.sleep(2)
        
        # Verify accounting configuration
        accounting_config = uut.execute("show running-config | include accounting")
        logger.info(f"Accounting config: {accounting_config}")
        
        if "aaa accounting commands" in accounting_config and tacacs_group_name in accounting_config:
            logger.info("Accounting successfully configured")
        else:
            all_aaa = uut.execute("show running-config | section aaa")
            logger.info(f"All AAA configurations: {all_aaa}")
            if f"aaa accounting commands {privilege_level}" in all_aaa and tacacs_group_name in all_aaa:
                logger.info("Accounting found in full AAA section")
            else:
                # One more try - check full running config
                full_config = uut.execute("show running-config")
                if f"aaa accounting commands {privilege_level} default start-stop group {tacacs_group_name}" in full_config:
                    logger.info("Accounting found in full running config")
                else:
                    self.failed("Accounting configuration failed or incomplete")

    @aetest.test
    def enable_tacacs_debugging(self, uut):
        """Enable TACACS accounting debug logs"""
        logger.info(banner("Enabling TACACS debugging"))
        
        # Enable TACACS and AAA debugging
        debug_commands = [
            "debug tacacs accounting",
            "debug tacacs events",
            "debug aaa accounting"
        ]
        
        for cmd in debug_commands:
            try:
                uut.execute(cmd)
                logger.info(f"Enabled: {cmd}")
            except Exception as e:
                logger.warning(f"Could not enable debug command {cmd}: {str(e)}")
        
        # Verify debugging is enabled
        debug_status = uut.execute("show debug")
        logger.info(f"Debug status: {debug_status}")
        
        # We'll continue even if not all debug options are available
        # as different platforms may support different debug options
