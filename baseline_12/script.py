from pyats import aetest
from pyats.log.utils import banner
import logging

logger = logging.getLogger(__name__)

# Custom parameters for reference:
# tacacs_server_name: 'TAC'
# tacacs_server_group: 'TAC_Grp'
# tacacs_ip: '10.76.239.47'
# tls_port: '6049'
# tls_idle_timeout: '61'
# tls_connection_timeout: '32'
# tls_retries: '2'
# source_interface: 'GigabitEthernet1'
# priv_level: '15'

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device via Telnet"""
        logger.info(banner("Connecting to the device via Telnet"))
        uut = testbed.devices['vwlc-ksukulka']
        uut.connect()
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    """Configure ISE to enable TACACS"""

    @aetest.test
    def enable_tacacs_on_ise(self):
        """Enable TACACS on ISE (manual/API step if needed)"""
        logger.info("Enable TACACS on ISE (manual/API step if needed)")
        # Placeholder for ISE configuration

class ConfigureTacacsServer(aetest.Testcase):
    """Configure TACACS server and enable authorization"""

    @aetest.test
    def configure_tacacs_server_and_group(self, uut):
        """Configure TACACS server with single connection and server group"""
        logger.info("Configuring TACACS server and group")
        try:
            uut.configure([
                "tacacs server TAC",
                " address ipv4 10.76.239.47",
                " single-connection",
                "aaa group server tacacs+ TAC_Grp",
                " server name TAC"
            ])
        except Exception as e:
            logger.error(f"Failed to configure TACACS server/group: {e}")
            self.failed("TACACS server/group configuration failed")

    @aetest.test
    def enable_authorization(self, uut):
        """Enable authorization with TACACS group of privilege 15"""
        logger.info("Enabling authorization with TACACS group")
        try:
            uut.configure([
                "aaa authentication login default group TAC_Grp local",
                "aaa authorization commands 15 default group TAC_Grp local"
            ])
        except Exception as e:
            logger.error(f"Failed to enable authorization: {e}")
            self.failed("Authorization configuration failed")

class VerifyAuthorization(aetest.Testcase):
    """Verify user authorization"""

    @aetest.test
    def execute_privileged_commands(self, uut):
        """Execute privilege level 15 commands on Telnet console"""
        logger.info("Executing privilege level 15 commands")
        try:
            output = uut.execute("show running-config", timeout=120)
            assert "Current configuration" in output, "Authorization failed"
            logger.info("Privilege level 15 command executed successfully")
        except Exception as e:
            logger.error(f"Failed to execute privileged commands: {e}")
            self.failed("Privilege command execution failed")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from the device"))
        uut.disconnect()
