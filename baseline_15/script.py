from pyats import aetest  # type: ignore
from pyats.log.utils import banner  # type: ignore
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        logger.info(banner("Connecting to the device via SSH"))
        uut = testbed.devices['uut']
        uut.connect()  # SSH is default
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    """Configure ISE to enable TACACS (placeholder)"""

    @aetest.test
    def enable_tacacs(self):
        logger.info("Configuring ISE to enable TACACS (manual or external step)")
        # Add your ISE configuration steps here if needed

class TacacsConfigurationTest(aetest.Testcase):
    """Test case to configure and verify TACACS"""

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure two TACACS servers in the same group"""
        logger.info("Configuring TACACS servers")
        try:
            commands = [
                f"tacacs server {uut.custom['tacacs_server1_name']}",
                f" address ipv4 {uut.custom['tacacs_server1_ip']}",
                " port 49",
                "!",
                f"tacacs server {uut.custom['tacacs_server2_name']}",
                f" address ipv4 {uut.custom['tacacs_server2_ip']}",
                " port 49",
                "!",
                f"aaa group server tacacs+ {uut.custom['tacacs_group_name']}",
                f" server name {uut.custom['tacacs_server1_name']}",
                f" server name {uut.custom['tacacs_server2_name']}",
                "!",
                f"aaa authentication login default group {uut.custom['tacacs_group_name']} local",
                f"aaa authorization commands 15 default group {uut.custom['tacacs_group_name']} local"
            ]
            uut.configure(commands)
            logger.info("TACACS servers configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure TACACS servers: {e}")
            self.failed(f"Failed to configure TACACS servers: {e}")

    @aetest.test
    def verify_authorization(self, uut):
        """Verify authorization by executing privilege level 15 CLI"""
        logger.info("Verifying authorization")
        try:
            output = uut.execute("show running-config")
            logger.debug(f"Authorization verification output:\n{output}")
            expected = f"aaa authorization commands 15 default group {uut.custom['tacacs_group_name']} local"
            if expected in output:
                self.passed("Authorization verified successfully")
            else:
                logger.error("Authorization verification failed. Expected configuration not found.")
                self.failed("Authorization verification failed")
        except Exception as e:
            logger.error(f"Failed to verify authorization: {e}")
            self.failed(f"Failed to verify authorization: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut=None):
        """Remove TACACS configuration"""
        logger.info(banner("Cleaning up TACACS configuration"))
        if not uut:
            uut = self.parent.parameters.get('uut')
            if not uut:
                self.failed("Device 'uut' is not available for cleanup")

        try:
            commands = [
                f"no tacacs server {uut.custom['tacacs_server1_name']}",
                f"no tacacs server {uut.custom['tacacs_server2_name']}",
                f"no aaa group server tacacs+ {uut.custom['tacacs_group_name']}",
                f"no aaa authentication login default group {uut.custom['tacacs_group_name']} local",
                f"no aaa authorization commands 15 default group {uut.custom['tacacs_group_name']} local"
            ]
            uut.configure(commands)
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            self.failed(f"Cleanup failed: {e}")
