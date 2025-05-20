from pyats import aetest
from pyats.log.utils import banner
import logging
import time
import re

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
        """Configure non-working and working TACACS servers in separate groups"""
        logger.info("Configuring TACACS servers and groups")
        commands = [
            "tacacs server NONWORKING_TAC",
            " address ipv4 10.1.1.1",
            " key cisco",
            " single-connection",
            " exit",
            "tacacs server WORKING_TAC",
            " address ipv4 10.76.239.47",
            " key cisco",
            " single-connection",
            " exit",
            "aaa group server tacacs+ NONWORKING_GRP",
            " server name NONWORKING_TAC",
            " exit",
            "aaa group server tacacs+ WORKING_GRP",
            " server name WORKING_TAC",
            " exit"
        ]
        uut.configure(commands)
        logger.info("TACACS servers and groups configured successfully")

    @aetest.test
    def enable_accounting(self, uut):
        """Enable accounting for privilege 15 with non-working then working group"""
        logger.info("Enabling accounting for privilege 15 with fallback")
        # First try with non-working group
        uut.configure([
            "aaa authentication login default group NONWORKING_GRP local",
            "aaa authorization commands 15 default group NONWORKING_GRP local",
            "aaa accounting commands 15 default start-stop group NONWORKING_GRP"
        ])
        # Now reconfigure to use working group as fallback
        uut.configure([
            "aaa authentication login default group WORKING_GRP local",
            "aaa authorization commands 15 default group WORKING_GRP local",
            "aaa accounting commands 15 default start-stop group WORKING_GRP"
        ])
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
        patterns = [
            r'accounting.*loopback123',
            r'accounting.*test_accounting',
            r'TACACS.*accounting',
            r'AAA.*accounting'
        ]
        found = any(re.search(p, debug_output, re.IGNORECASE) for p in patterns)
        if found:
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
            "no tacacs server NONWORKING_TAC",
            "no tacacs server WORKING_TAC",
            "no aaa group server tacacs+ NONWORKING_GRP",
            "no aaa group server tacacs+ WORKING_GRP",
            "no aaa authentication login default group NONWORKING_GRP local",
            "no aaa authentication login default group WORKING_GRP local",
            "no aaa authorization commands 15 default group NONWORKING_GRP local",
            "no aaa authorization commands 15 default group WORKING_GRP local",
            "no aaa accounting commands 15 default group NONWORKING_GRP",
            "no aaa accounting commands 15 default group WORKING_GRP"
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
