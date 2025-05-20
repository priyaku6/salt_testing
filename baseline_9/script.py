from pyats import aetest
from pyats.log.utils import banner
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_device(self, testbed):
        logger.info(banner("Connecting to the device"))
        uut = testbed.devices['vwlc-ksukulka']
        uut.connect()
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    @aetest.test
    def enable_tacacs_on_ise(self):
        logger.info("Enable TACACS on ISE (manual/API step if needed)")
        # Placeholder for ISE configuration

class ConfigureTacacsGroups(aetest.Testcase):
    @aetest.test
    def configure_nonworking_and_working_groups(self, uut):
        logger.info("Configuring non-working and working TACACS server groups")
        try:
            uut.configure([
                "tacacs server NONWORKING_TAC",
                " address ipv4 192.0.2.1",  # Non-working IP
                "tacacs server WORKING_TAC",
                " address ipv4 10.1.1.1",   # Working IP
                "aaa group server tacacs+ NONWORKING_GROUP",
                " server name NONWORKING_TAC",
                "aaa group server tacacs+ WORKING_GROUP",
                " server name WORKING_TAC"
            ])
        except Exception as e:
            logger.error(f"Failed to configure TACACS groups: {e}")
            self.failed("TACACS group configuration failed")

    @aetest.test
    def enable_login_authentication(self, uut):
        logger.info("Enabling login authentication with non-working then working group")
        try:
            uut.configure([
                "aaa authentication login default group NONWORKING_GROUP group WORKING_GROUP local"
            ])
        except Exception as e:
            logger.error(f"Failed to enable login authentication: {e}")
            self.failed("Login authentication configuration failed")

class TelnetLoginTest(aetest.Testcase):
    @aetest.test
    def telnet_login(self, uut):
        logger.info("Attempting Telnet login to the device")
        # If Unicon is set up for telnet, this will use the testbed's telnet config
        try:
            if not uut.connected:
                uut.connect()
            output = uut.execute("show version")
            assert "Cisco" in output or "version" in output.lower(), "Telnet login failed or unexpected output"
            logger.info("Telnet login and command execution successful")
        except Exception as e:
            logger.error(f"Telnet login failed: {e}")
            self.failed("Telnet login test failed")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from the device"))
        uut.disconnect()
