from pyats import aetest  # type: ignore
import logging
import paramiko  # For SSH connection

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

    @aetest.test
    def configure_tacacs_server(self, uut):
        """Configure TACACS server with single connection and server group"""
        logger.info("Configuring TACACS server...")
        
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
    def ssh_to_device(self, uut):
        """Attempt SSH to the device and verify login"""
        logger.info("Attempting SSH to the device...")
        
        # Retrieve required parameters
        ssh_connection = uut.connections.get('ssh')
        if not ssh_connection:
            self.failed("SSH connection is not defined in the testbed configuration")
            return
        
        device_ip = ssh_connection.get('ip')
        username = uut.credentials['default']['username']
        password = uut.credentials['default']['password']
        
        if not device_ip or not isinstance(device_ip, str) or not username or not password:
            self.failed("Device IP, username, or password is not properly defined in the testbed configuration")
            return
        
        # Attempt SSH connection
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=device_ip, username=username, password=password)
            
            # Execute a command to verify login
            stdin, stdout, stderr = ssh_client.exec_command("show running-config | include hostname")
            output = stdout.read().decode()
            logger.info(f"SSH command output: {output}")
            
            if "hostname" in output:
                self.passed("SSH login successful and command executed")
            else:
                self.failed("SSH login successful but command output is unexpected")
        except Exception as e:
            self.failed(f"SSH login failed: {e}")
        finally:
            ssh_client.close()

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test execution"""

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info("Disconnecting from the device...")
        uut.disconnect()
