from pyats import aetest
from pyats.log.utils import banner
import logging
import re
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
            "tacacs server NONWORKING_TAC",
            " address ipv4 10.1.1.1",
            " key cisco",
            " single-connection",
            " exit",
            "tacacs server TAC",
            " address ipv4 10.76.239.47",
            " key cisco",
            " single-connection",
            " exit",
            "aaa group server tacacs+ TAC_Grp",
            " server name NONWORKING_TAC",
            " server name TAC",
            " exit"
        ]
        try:
            uut.configure(commands)
            logger.info("TACACS servers and group configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure TACACS servers/group: {e}")
            self.failed("Failed to configure TACACS servers/group")

    @aetest.test
    def enable_accounting(self, uut):
        """Enable accounting for privilege 15 with TACACS group"""
        logger.info("Enabling accounting for privilege 15")
        commands = [
            "aaa authentication login default group TAC_Grp local",
            "aaa authorization commands 15 default group TAC_Grp local",
            "aaa accounting commands 15 default start-stop group TAC_Grp"
        ]
        try:
            uut.configure(commands)
            uut.execute("debug aaa accounting")
            logger.info("Accounting enabled for privilege 15 commands and debug enabled")
        except Exception as e:
            logger.error(f"Failed to enable accounting: {e}")
            self.failed("Failed to enable accounting")

    @aetest.test
    def execute_privilege_command(self, uut):
        """Execute privilege 15 config command to trigger accounting"""
        logger.info("Executing privilege 15 config command (interface loopback123)")
        try:
            uut.configure([
                "interface loopback123",
                "description test_accounting",
                "exit"
            ])
            logger.info("Config command executed successfully")
            time.sleep(5)  # Wait for logs to be written
        except Exception as e:
            logger.error(f"Failed to execute config command: {e}")
            self.failed("Config command failed or not authorized")

    @aetest.test
    def verify_accounting(self, uut):
        """Verify accounting is successful using debug logs"""
        logger.info("Verifying accounting via debug logs")
        try:
            debug_output = uut.execute("show logging | include accounting|TACACS|loopback123|test_accounting|ksukulka")
            logger.debug(f"Debug log output:\n{debug_output}")
            patterns = [
                r'accounting.*loopback123',
                r'accounting.*test_accounting',
                r'TACACS.*accounting',
                r'AAA.*accounting',
                r'ksukulka.*accounting'
            ]
            found = any(re.search(p, debug_output, re.IGNORECASE) for p in patterns)
            if found:
                self.passed("Accounting verified successfully in debug logs")
            else:
                logger.error("Accounting verification failed. No accounting record found for the config command.")
                logger.error("Tip: Manually check 'show logging' on the device for accounting records after running a config command.")
                self.failed("Accounting verification failed")
        except Exception as e:
            logger.error(f"Failed to verify accounting: {e}")
            self.failed(f"Failed to verify accounting: {e}")

    @aetest.cleanup
    def cleanup(self, uut):
        """Cleanup configuration"""
        logger.info("Cleaning up test configuration")
        try:
            uut.configure([
                "no interface loopback123",
                "no tacacs server NONWORKING_TAC",
                "no tacacs server TAC",
                "no aaa group server tacacs+ TAC_Grp",
                "no aaa authentication login default group TAC_Grp local",
                "no aaa authorization commands 15 default group TAC_Grp local",
                "no aaa accounting commands 15 default group TAC_Grp"
            ])
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        """Disconnect from the device"""
        uut = self.parent.parameters.get('uut')
        if uut and uut.connected:
            uut.disconnect()
            logger.info("Disconnected from device")
