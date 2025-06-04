__author__ = "Priya kumari"
__copyright__ = "Copyright 2025, Cisco Systems"
__maintainer__ = "AAA Dev team"
__email__ = "aaa-dev@cisco.com"
__date__ = "11 April, 2025"
__version__ = 1.0

import logging
import time
from pyats import aetest # type: ignore
from pyats.log.utils import banner # type: ignore

# Create logger
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
        try:
            uut = testbed.devices['uut']
            testscript.parameters['uut'] = uut
            
            # Initialize variables from testbed custom section with defaults
            required_params = [
                'working_server_name', 'nonworking_server_name', 
                'working_server_ip', 'nonworking_server_ip', 
                'working_server_key', 'nonworking_server_key',
                'working_server_group', 'nonworking_server_group', 
                'tacacs_port', 'privilege_level', 'test_command'
            ]
            
            # Set default values
            default_values = {
                'working_server_name': 'TACACS_WORKING',
                'nonworking_server_name': 'TACACS_NONWORKING',
                'working_server_ip': '10.1.1.1',
                'nonworking_server_ip': '192.168.255.255',
                'working_server_key': 'cisco123',
                'nonworking_server_key': 'cisco123',
                'working_server_group': 'TACACS_WORKING_GROUP',
                'nonworking_server_group': 'TACACS_NONWORKING_GROUP',
                'tacacs_port': '49',
                'privilege_level': '15',
                'test_command': 'show version'
            }
            
            # Try to get values from testbed, use
            for param in required_params:
                value = testbed.custom.get(param, default_values[param])
                testscript.parameters[param] = value
        except KeyError as e:
            self.failed(f"Missing required parameter in testbed: {e}")
        except Exception as e:
            self.failed(f"Error during variable initialization: {e}")
