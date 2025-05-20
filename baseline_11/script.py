from pyats import aetest  # type: ignore
from pyats.log.utils import banner  # type: ignore
import logging
from unicon.eal.dialogs import Dialog, Statement  # type: ignore

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device"""
        logger.info(banner("Connecting to the device"))
        uut = testbed.devices['vwlc-ksukulka']
        uut.connect()
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    """Configure ISE to enable TACACS"""

    @aetest.test
    def enable_tacacs_on_ise(self, uut):
        """Enable TACACS on ISE (simulated)"""
        logger.info("Enabling TACACS on ISE (manual/REST API step if needed)")
        # Add your ISE configuration steps here if you have API access
        # Otherwise, this is a placeholder for manual/GUI configuration

class ConfigureTacacsServers(aetest.Testcase):
    """Configure TACACS servers and enable authorization"""

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure TACACS server with single connection and server group"""
        logger.info("Configuring TACACS servers and group")
        try:
            uut.configure([
                "tacacs server TAC1",
                " address ipv4 10.1.1.1",
                " single-connection",
                "tacacs server TAC2",
                " address ipv4 10.1.1.2",
                " single-connection",
                "aaa group server tacacs+ TAC_GROUP",
                " server name TAC1",
                " server name TAC2"
            ])
        except Exception as e:
            logger.error(f"Failed to configure TACACS servers: {e}")
            self.failed("TACACS server configuration failed")

    @aetest.test
    def enable_authorization(self, uut):
        """Enable authorization with TACACS group of privilege 15"""
        logger.info("Enabling authorization with TACACS group")
        try:
            uut.configure([
                "aaa authentication login default group TAC_GROUP local",
                "aaa authorization commands 15 default group TAC_GROUP local"
            ])
        except Exception as e:
            logger.error(f"Failed to enable authorization: {e}")
            self.failed("Authorization configuration failed")

class VerifyAuthorization(aetest.Testcase):
    """Verify user authorization"""

    @aetest.test
    def execute_privileged_commands(self, uut):
        """Execute privilege level 15 commands"""
        logger.info("Executing privilege level 15 commands")
        try:
            output = uut.execute("show running-config", timeout=120)
            assert "Current configuration" in output, "Authorization failed"
            logger.info("Privilege level 15 command executed successfully")
        except Exception as e:
            logger.error(f"Failed to execute privileged commands: {e}")
            self.failed("Privilege command execution failed")

    @aetest.test
    def verify_ssh_login(self, uut):
        """Verify SSH login with TACACS servers"""
        logger.info("Verifying SSH login (manual/automated step)")
        # If you want to automate SSH login verification, use paramiko or expect
        # Otherwise, this is a placeholder for manual verification
        logger.info("SSH login verified successfully (placeholder)")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from the device"))
        uut.disconnect()
