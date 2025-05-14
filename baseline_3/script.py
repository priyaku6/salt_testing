import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_testbed(self, testbed):
        """Validate the testbed information"""
        logger.info(banner("Validating Testbed"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def connect_device(self, testbed):
        """Connect to the device"""
        logger.info(banner("Connecting to the device"))
        uut = testbed.devices.get('vwlc-ksukulka')  # Ensure the device name matches the testbed
        if not uut:
            self.failed("Device 'vwlc-ksukulka' not found in testbed")
        try:
            uut.connect()
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
            self.parent.parameters['uut'] = uut  # Pass the device to test cases
        except Exception as e:
            self.failed(f"Failed to connect to device: {e}")


class ConfigureTacacsServer(aetest.Testcase):
    """Test case to configure TACACS server"""

    @aetest.test
    def configure_tacacs(self, uut):
        """Configure TACACS server"""
        logger.info("Configuring TACACS server")
        
        # Retrieve required custom parameters
        tacacs_server_name = uut.custom.get('tacacs_server_name')
        tacacs_ip_working = uut.custom.get('tacacs_ip_working')
        
        if not tacacs_server_name or not tacacs_ip_working:
            self.failed("TACACS server name or IP is not defined in the testbed configuration")
            return
        
        # TACACS server configuration commands
        tacacs_server_config = [
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 {tacacs_ip_working}",
            " key cisco",
            " single-connection"
        ]
        
        try:
            uut.configure(tacacs_server_config)
            logger.info("TACACS server configuration completed")
        except Exception as e:
            self.failed(f"Failed to configure TACACS server: {e}")


class VerifyTacacsLogin(aetest.Testcase):
    """Test case to verify TACACS login"""

    @aetest.test
    def verify_login(self, uut):
        """Verify login using TACACS"""
        logger.info("Verifying TACACS login")
        try:
            output = uut.execute("show tacacs")
            logger.info(f"TACACS server status: {output}")

            if "Server Status: Alive" in output:
                self.passed("TACACS login verification successful")
            else:
                logger.error("TACACS server is not reachable or not configured correctly")
                self.failed("TACACS login verification failed")
        except Exception as e:
            self.failed(f"Failed to verify TACACS login: {e}")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self):
        """Remove TACACS server configuration"""
        logger.info(banner("Cleaning up TACACS configuration"))
        uut = self.parent.parameters.get('uut')  # Retrieve uut from parent parameters
        if not uut:
            self.failed("Device 'uut' not found in parameters")
        try:
            uut.configure(["no tacacs server TAC"])
            logger.info("TACACS configuration cleanup completed")
        except Exception as e:
            self.failed(f"Failed to clean up TACACS configuration: {e}")

    @aetest.subsection
    def disconnect_device(self):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        uut = self.parent.parameters.get('uut')  # Retrieve uut from parent parameters
        if not uut:
            self.failed("Device 'uut' not found in parameters")
        try:
            uut.disconnect()
            logger.info("Device disconnected successfully")
        except Exception as e:
            self.failed(f"Failed to disconnect device: {e}")
