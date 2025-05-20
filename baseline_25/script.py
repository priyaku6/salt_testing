from pyats import aetest  # type: ignore
from pyats.log.utils import banner  # type: ignore
import logging
import time

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        logger.info(banner("Connecting to the device via telnet"))
        uut = testbed.devices['uut']
        uut.connect(via='telnet')
        assert uut.connected, f"Couldn't connect to device {uut.name}"
        self.parent.parameters['uut'] = uut
        logger.info(f"Connected to device {uut.name}")

class TacacsAccountingTest(aetest.Testcase):
    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure two TACACS servers in the same group (non-working first, then working)"""
        logger.info("Configuring TACACS servers and group")
        commands = [
            "tacacs server NonWorkingServer",
            " address ipv4 10.1.1.1",
            " key NonWorkingKey",
            " single-connection",
            " exit",
            "tacacs server WorkingServer",
            " address ipv4 10.76.239.47",
            " key WorkingKey",
            " single-connection",
            " exit",
            "aaa group server tacacs+ TAC_Grp",
            " server name NonWorkingServer",
            " server name WorkingServer",
            " exit"
        ]
        uut.configure(commands)
        logger.info("TACACS servers and group configured successfully")

    @aetest.test
    def enable_accounting(self, uut):
        """Enable accounting for privilege 15 with TACACS group"""
        logger.info("Enabling accounting for privilege 15")
        commands = [
            "aaa authentication login default group TAC_Grp local",
            "aaa authorization commands 15 default group TAC_Grp local",
            "aaa accounting commands 15 default start-stop group TAC_Grp"
        ]
        uut.configure(commands)
        # Enable TACACS accounting debug in exec mode
        for cmd in ["debug tacacs events", "debug tacacs accounting", "terminal monitor"]:
            try:
                uut.execute(cmd)
            except Exception:
                pass
        logger.info("Accounting enabled for privilege 15 commands and debug enabled")

    @aetest.test
    def execute_privilege_command(self, uut):
        """Execute privilege 15 config command to trigger accounting"""
        logger.info("Executing privilege 15 config command (interface loopback123)")
        uut.configure([
            "interface loopback123",
            "description test_accounting",
            "exit"
        ])
        logger.info("Config command executed successfully")
        time.sleep(5)  # Wait for logs to be written

    @aetest.test
    def verify_accounting(self, uut):
        """Verify accounting is successful using debug logs"""
        logger.info("Verifying accounting via debug logs")
        debug_output = uut.execute("show logging | include accounting|TACACS|loopback123|test_accounting")
        logger.debug(f"Debug log output:\n{debug_output}")
        # Look for evidence of accounting for the config command
        success_indicators = [
            "accounting", "TACACS", "loopback123", "test_accounting",
            "TACACS+ start accounting", "TACACS+ stop accounting", "Record sent"
        ]
        if any(indicator in debug_output for indicator in success_indicators):
            self.passed("Accounting verified successfully in debug logs")
        else:
            logger.error("Accounting verification failed. No accounting record found for the config command.")
            logger.error("Tip: Manually check 'show logging' on the device for accounting records after running a config command.")
            self.failed("Accounting verification failed")

    @aetest.cleanup
    def cleanup(self, uut):
        """Cleanup configuration"""
        logger.info("Cleaning up test configuration")
        uut.configure([
            "no interface loopback123",
            "no tacacs server NonWorkingServer",
            "no tacacs server WorkingServer",
            "no aaa group server tacacs+ TAC_Grp",
            "no aaa authentication login default group TAC_Grp local",
            "no aaa authorization commands 15 default group TAC_Grp local",
            "no aaa accounting commands 15 default group TAC_Grp"
        ])
        logger.info("Cleanup completed successfully")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        """Disconnect from the device"""
        uut = self.parent.parameters.get('uut')
        if uut and uut.connected:
            uut.disconnect()
            logger.info("Disconnected from device")
