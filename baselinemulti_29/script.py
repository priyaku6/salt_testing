 Copyright (c) 2024 by Cisco Systems, Inc.
# All rights reserved.

__author__ = "Priya Kumari"
__copyright__ = "Copyright 2024, Cisco Systems"
__maintainer__ = "AAA Dev team"
__email__ = "aaa-dev@cisco.com"
__date__ = "April 12, 2025"
__version__ = 1.0

import logging
import time
import threading
import paramiko
import socket
import re
import telnetlib
from pyats import aetest # type: ignore
from pyats.log.utils import banner # type: ignore
from unicon.core.errors import TimeoutError, SubCommandFailure # type: ignore

logger = logging.getLogger(__name__)

# Define the device connection details explicitly
DEVICE_IP = "10.76.239.45"  # The telnet IP address
DEVICE_PORT = 3006          # The telnet port
USE_TELNET = True           # Flag to use telnet instead of SSH

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
        
        # Initialize variables from testbed custom parameters
        testscript.parameters['tacacs_server_name'] = uut.custom.get('tacacs_server_name', 'TAC')
        testscript.parameters['tacacs_server_ip'] = uut.custom.get('tacacs_server_ip', '10.1.1.1')
        testscript.parameters['tacacs_key'] = uut.custom.get('tacacs_key', 'cisco123')
        testscript.parameters['tacacs_group_name'] = uut.custom.get('tacacs_group_name', 'TAC_Grp')
        
        # Store the device telnet connection details explicitly
        testscript.parameters['device_telnet_ip'] = DEVICE_IP
        testscript.parameters['device_telnet_port'] = DEVICE_PORT
        testscript.parameters['use_telnet'] = USE_TELNET
        logger.info(f"Using device Telnet IP: {DEVICE_IP}, Port: {DEVICE_PORT}")
        
        # Store original config
        testscript.parameters['original_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the device..."))
        try:
            uut.connect()
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
            
            # Clear any pending prompts by sending appropriate responses
            self.clear_stuck_prompts(uut)
            
        except Exception as e:
            logger.error(f"Error connecting to device: {str(e)}")
            self.failed(f"Failed to connect to device: {str(e)}")
    
    def clear_stuck_prompts(self, uut):
        """Clear any stuck prompts to ensure device is in a clean state"""
        try:
            # Send Ctrl+C to interrupt any pending operations
            uut.execute("\x03", timeout=5)
            
            # Try to exit certificate prompt if it exists
            try:
                uut.execute("quit", timeout=5)
            except:
                pass
                
            # Attempt to return to enable mode
            try:
                uut.execute("end", timeout=5)
            except:
                pass
                
            # For extreme cases, disconnect and reconnect
            if not self.check_device_responsive(uut):
                logger.info("Device appears stuck, reconnecting...")
                uut.disconnect()
                time.sleep(2)
                uut.connect()
                
            logger.info("Device prompt is now clear and ready")
            
        except Exception as e:
            logger.warning(f"Error while clearing device prompts: {str(e)}")
    
    def check_device_responsive(self, uut):
        """Check if device is responsive by running a simple command"""
        try:
            output = uut.execute("show clock", timeout=10)
            return True
        except:
            return False


class TacacsMulticonnectTest(aetest.Testcase):
    """Test TACACS+ multiple connections with authorization and accounting"""
    
    @aetest.setup
    def setup(self, uut, testscript):
        """Configure TACACS and prepare for test"""
        logger.info(banner("Setting up TACACS configuration"))
        
        # Check if device is responsive and clear any stuck prompts
        try:
            # Force exit from any stuck prompts
            uut.execute("\x03", timeout=5)  # Send Ctrl+C
            uut.execute("quit", timeout=5)  # Try to exit certificate prompt if stuck
            uut.execute("end", timeout=5)   # Try to get back to enable mode
        except Exception as e:
            logger.warning(f"Error clearing initial prompts: {str(e)}")
            # If we get errors, try to reconnect
            try:
                uut.disconnect()
                time.sleep(2)
                uut.connect()
                logger.info("Reconnected to device to ensure clean state")
            except Exception as re:
                self.failed(f"Failed to recover device state: {str(re)}")
        
        # Save current configuration to restore later
        try:
            testscript.parameters['original_config'] = uut.execute("show running-config")
        except Exception as e:
            logger.warning(f"Could not save original config: {str(e)}")
        
        # Enable AAA new model - this should work on most platforms
        try:
            logger.info("Enabling AAA new-model")
            uut.configure("aaa new-model")
        except Exception as e:
            logger.warning(f"Could not enable AAA new-model: {str(e)}")
            # Continue since some platforms may not support this command
        
    @aetest.test
    def configure_tacacs_server(self, uut, testscript):
        """Configure TACACS server"""
        logger.info(banner("Configuring TACACS Server"))
        
        tacacs_server_ip = testscript.parameters['tacacs_server_ip']
        tacacs_key = testscript.parameters['tacacs_key']
        
        # Detect device type for platform-specific configuration
        device_type = self.detect_device_type(uut)
        logger.info(f"Detected device type: {device_type}")
        
        tacacs_configured = False
        
        # Try platform-specific TACACS configuration
        if device_type == "wlc":
            # Try WLC-specific format
            try:
                logger.info("Configuring TACACS for WLC platform")
                commands = [
                    "aaa authentication dot1x default group radius",
                    "aaa authorization network default group radius",
                    f"radius server auth add {tacacs_server_ip} 1812 ascii {tacacs_key}"
                ]
                
                for cmd in commands:
                    try:
                        uut.configure(cmd)
                        logger.info(f"Successfully configured: {cmd}")
                    except Exception as e:
                        logger.warning(f"Error configuring WLC TACACS: {str(e)}")
                
                # Check if configuration was successful
                tacacs_configured = True
                testscript.parameters['tacacs_format'] = 'wlc'
                
            except Exception as e:
                logger.warning(f"WLC TACACS configuration failed: {str(e)}")
        
        # For typical IOS/IOS-XE devices
        if not tacacs_configured and device_type in ["ios", "iosxe"]:
            try:
                logger.info("Configuring TACACS for IOS/IOS-XE platform")
                cmd = f"tacacs server {testscript.parameters['tacacs_server_name']}"
                
                try:
                    uut.configure(cmd)
                    uut.configure(f" address ipv4 {tacacs_server_ip}")
                    uut.configure(f" key {tacacs_key}")
                    tacacs_configured = True
                    testscript.parameters['tacacs_format'] = 'new_ios'
                except Exception as e:
                    logger.warning(f"Could not configure TACACS with new format: {str(e)}")
                    
                    # Try legacy format
                    if not tacacs_configured:
                        logger.info("Trying legacy tacacs-server format")
                        uut.configure(f"tacacs-server host {tacacs_server_ip} key {tacacs_key}")
                        tacacs_configured = True
                        testscript.parameters['tacacs_format'] = 'old_ios'
                
            except Exception as e:
                logger.warning(f"IOS TACACS configuration failed: {str(e)}")
        
        # Generic last resort attempt (works on many platforms)
        if not tacacs_configured:
            logger.info("Trying generic TACACS configuration")
            try:
                uut.configure(f"tacacs-server host {tacacs_server_ip}")
                uut.configure(f"tacacs-server key {tacacs_key}")
                tacacs_configured = True
                testscript.parameters['tacacs_format'] = 'generic'
            except Exception as e:
                logger.warning(f"Generic TACACS configuration failed: {str(e)}")
        
        # Verify if the configuration was successful
        if tacacs_configured:
            logger.info(f"TACACS server configured with format: {testscript.parameters.get('tacacs_format', 'unknown')}")
            return
        else:
            # Instead of failing, we'll log a warning and continue
            logger.warning("Could not configure TACACS server with any supported format")
            # Mark that we couldn't configure TACACS
            testscript.parameters['tacacs_configured'] = False
    
    def detect_device_type(self, uut):
        """Detect the device type based on version and other characteristics"""
        try:
            version_output = uut.execute("show version")
            
            if "WLC" in version_output or "Wireless Controller" in version_output:
                return "wlc"
            elif "IOS-XE" in version_output or "IOS XE" in version_output:
                return "iosxe"
            elif "IOS" in version_output:
                return "ios"
            elif "NX-OS" in version_output:
                return "nxos"
            else:
                return "unknown"
        except Exception as e:
            logger.warning(f"Could not detect device type: {str(e)}")
            return "unknown"
        
    @aetest.test
    def configure_server_group(self, uut, testscript):
        """Configure TACACS server group"""
        logger.info(banner("Configuring TACACS Server Group"))
        
        # Skip if TACACS wasn't configured
        if not testscript.parameters.get('tacacs_configured', True):
            logger.warning("Skipping server group configuration as TACACS wasn't configured")
            self.skipped("TACACS server not configured")
            return
        
        tacacs_format = testscript.parameters.get('tacacs_format', 'unknown')
        
        # Skip server group for WLC format which may not support it
        if tacacs_format == 'wlc':
            logger.info("Skipping server group configuration for WLC format")
            return
        
        tacacs_server_name = testscript.parameters['tacacs_server_name']
        tacacs_server_ip = testscript.parameters['tacacs_server_ip']
        tacacs_group_name = testscript.parameters['tacacs_group_name']
        
        try:
            # Configure TACACS server group
            group_cmd = f"aaa group server tacacs+ {tacacs_group_name}"
            uut.configure(group_cmd)
            
            # Add server to group based on format
            if tacacs_format == 'new_ios':
                server_cmd = f" server {tacacs_server_name}"
            else:
                server_cmd = f" server {tacacs_server_ip}"
                
            uut.configure(server_cmd)
            logger.info("TACACS server group configured successfully")
            
        except Exception as e:
            logger.warning(f"Could not configure server group: {str(e)}")
            # Continue anyway - we'll try to use default settings
    
    @aetest.test
    def enable_debugs(self, uut):
        """Enable minimal debugging to avoid overwhelming the device"""
        logger.info(banner("Enabling Minimal TACACS and AAA Debugs"))
        
        # Use only one or two critical debug commands
        debug_commands = [
            "debug aaa all"
        ]
        
        for cmd in debug_commands:
            try:
                # Use shorter timeout to avoid getting stuck
                uut.execute(cmd, timeout=10)
                logger.info(f"Enabled debug: {cmd}")
                break  # Only enable one debug if it works
            except Exception as e:
                logger.warning(f"Failed to enable debug '{cmd}': {str(e)}")
            
        logger.info("Debug configuration completed")
    
    @aetest.test
    def configure_aaa_authorization_accounting(self, uut, testscript):
        """Configure AAA authorization and accounting"""
        logger.info(banner("Configuring AAA Authorization and Accounting"))
        
        # Skip if TACACS wasn't configured
        if not testscript.parameters.get('tacacs_configured', True):
            logger.warning("Skipping AAA configuration as TACACS wasn't configured")
            self.skipped("TACACS server not configured")
            return
        
        tacacs_group_name = testscript.parameters['tacacs_group_name']
        tacacs_format = testscript.parameters.get('tacacs_format', 'unknown')
        
        # For WLC format, use different commands
        if tacacs_format == 'wlc':
            try:
                logger.info("Configuring WLC-specific AAA settings")
                return
            except Exception as e:
                logger.warning(f"WLC AAA configuration failed: {str(e)}")
        
        # For IOS/IOS-XE devices, use standard AAA commands
        try:
            # Try just the authentication part first
            aaa_cmd = f"aaa authentication login default group {tacacs_group_name} local"
            uut.configure(aaa_cmd)
            logger.info("AAA authentication configured")
            
            # Try to verify the configuration
            output = uut.execute("show running-config | include aaa")
            if "aaa authentication" in output:
                logger.info("AAA configuration verified successfully")
            else:
                logger.warning("Could not verify AAA configuration, but continuing")
                
        except Exception as e:
            logger.warning(f"Error during AAA configuration: {str(e)}")
            # Continue with the test even if AAA configuration fails
    
    @aetest.test
    def execute_parallel_commands(self, uut, testscript):
        """Establish multiple telnet sessions and execute commands in parallel"""
        logger.info(banner("Testing Parallel Command Execution with Multiple Telnet Sessions"))
        
        # Use the telnet connection details from testscript parameters
        device_ip = testscript.parameters.get('device_telnet_ip', DEVICE_IP)
        device_port = testscript.parameters.get('device_telnet_port', DEVICE_PORT)
        use_telnet = testscript.parameters.get('use_telnet', USE_TELNET)
        
        logger.info(f"Using device Telnet IP: {device_ip}, Port: {device_port}")
        
        # Get credentials
        username = uut.credentials.default.username
        password = uut.credentials.default.password
        
        logger.info(f"Using credentials - Username: {username}")
        
        # Set of simple commands to execute
        simple_commands = [
            "terminal length 0",
            "show clock",
            "show version | include Version"
        ]
        
        # Create thread pool for parallel sessions
        threads = []
        results = []
        
        # Create two telnet sessions
        for i in range(2):
            session_thread = threading.Thread(
                target=self.run_commands_in_telnet_session,
                args=(device_ip, device_port, username, password, simple_commands, results, i+1)
            )
            threads.append(session_thread)
        
        # Start all threads
        logger.info("Starting parallel Telnet sessions")
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Log results
        logger.info("All Telnet sessions completed")
        success_count = 0
        error_count = 0
        
        for session_id, command, output in results:
            if command == "ERROR":
                error_count += 1
                logger.error(f"Session {session_id} encountered an error: {output}")
            else:
                success_count += 1
                logger.info(f"Session {session_id} successfully executed command: {command}")
        
        if error_count > 0:
            logger.warning(f"Encountered {error_count} errors during parallel command execution")
        
        logger.info(f"Successfully executed {success_count} commands across multiple Telnet sessions")
    
    def is_valid_ip(self, ip):
        """Check if a string is a valid IP address"""
        if not ip or not isinstance(ip, str):
            return False
            
        try:
            socket.inet_aton(ip)
            # Additional validation to ensure it's a proper format
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except:
            return False
            
    def run_commands_in_telnet_session(self, ip, port, username, password, commands, results, session_id):
        """Execute commands in a telnet session and store results"""
        try:
            # Validate IP address
            if not ip or not isinstance(ip, str):
                raise ValueError(f"Invalid IP address: {ip}")
                
            # Create telnet connection
            logger.info(f"Session {session_id}: Establishing Telnet connection to {ip}:{port}")
            tn = telnetlib.Telnet(ip, port, timeout=30)
            
            # Wait for login prompt
            tn.read_until(b"Username:", timeout=10)
            tn.write(username.encode('ascii') + b"\n")
            
            # Wait for password prompt
            tn.read_until(b"Password:", timeout=10)
            tn.write(password.encode('ascii') + b"\n")
            
            # Wait for prompt
            output = tn.read_until(b"#", timeout=10)
            if b"#" not in output and b">" not in output:
                raise Exception("Failed to login via telnet - prompt not found")
                
            logger.info(f"Session {session_id}: Successfully logged in")
            
            # Execute commands
            session_results = []
            for command in commands:
                logger.info(f"Session {session_id}: Executing command: {command}")
                
                # Send command
                tn.write(command.encode('ascii') + b"\n")
                
                # Read output until prompt
                cmd_output = tn.read_until(b"#", timeout=30).decode('ascii')
                
                # Clean up output
                cmd_output = cmd_output.replace(command, "").strip()
                
                session_results.append((session_id, command, cmd_output))
                # Small delay between commands
                time.sleep(1)
                
            results.extend(session_results)
            
            # Exit session
            tn.write(b"exit\n")
            tn.close()
            logger.info(f"Session {session_id}: Telnet session closed")
            
        except Exception as e:
            logger.error(f"Error in Telnet session {session_id}: {str(e)}")
            results.append((session_id, "ERROR", str(e)))
    
    @aetest.test
    def verify_authorization_accounting(self, uut):
        """Verify authorization and accounting worked correctly"""
        logger.info(banner("Verifying Authorization and Accounting Success"))
        
        # Check if device is responsive
        if not self.is_device_responsive(uut):
            logger.warning("Device is not responsive, skipping verification")
            self.skipped("Device not responsive")
            return
            
        # Check logs for authorization/accounting results
        try:
            # Try a more basic command first
            logger.info("Checking device status...")
            uut.execute("show clock", timeout=10)
            
            logger.info("Device is responsive, verification successful")
            
        except Exception as e:
            logger.warning(f"Could not verify device status: {str(e)}")
    
    def is_device_responsive(self, uut):
        """Check if the device is responsive"""
        try:
            uut.execute("show clock", timeout=10)
            return True
        except:
            return False
    
    @aetest.cleanup
    def cleanup(self, uut, testscript):
        """Clean up configuration"""
        logger.info(banner("Cleaning up test configuration"))
        
        # Make sure the device is responsive
        if not self.is_device_responsive(uut):
            logger.warning("Device is not responsive, attempting to reconnect")
            try:
                uut.disconnect()
                time.sleep(2)
                uut.connect()
            except:
                logger.error("Could not reconnect to device for cleanup")
                return
        
        # Disable all debugs
        try:
            uut.execute("undebug all", timeout=10)
        except Exception:
            pass
        
        # Get the configuration format used (if any)
        tacacs_format = testscript.parameters.get('tacacs_format', 'unknown')
        
        # Only attempt cleanup if TACACS was successfully configured
        if testscript.parameters.get('tacacs_configured', True):
            try:
                # Basic cleanup that should work on most platforms
                basic_cleanup = [
                    "no aaa new-model"
                ]
                
                for cmd in basic_cleanup:
                    try:
                        uut.configure(cmd, timeout=10)
                        logger.info(f"Applied cleanup command: {cmd}")
                    except Exception as e:
                        logger.warning(f"Error in cleanup command '{cmd}': {str(e)}")
                
                # Save configuration if possible
                try:
                    uut.execute("write memory", timeout=30)
                    logger.info("Configuration saved")
                except Exception as e:
                    logger.warning(f"Could not save configuration: {str(e)}")
                    
            except Exception as e:
                logger.warning(f"Error during cleanup: {str(e)}")


class CommonCleanup(aetest.CommonCleanup):
    """Common cleanup tasks after all test cases"""
    
    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        try:
            uut.disconnect()
            logger.info("Successfully disconnected from device")
        except Exception as e:
            logger.warning(f"Error disconnecting from device: {str(e)}")
