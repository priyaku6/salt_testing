from pyats import aetest
from pyats.log.utils import banner
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        logger.info(banner("Connecting to the device..."))
        uut = testbed.devices['uut']
        uut.connect(via='telnet')
        assert uut.connected, f"Couldn't connect to device {uut.name}"
        self.parent.parameters['uut'] = uut
        logger.info(f"Connected to device {uut.name}")

class ConfigureTacacs(aetest.Testcase):
    @aetest.test
    def configure_tacacs_server(self):
        """Configure TACACS server with single connection"""
        logger.info("Configuring TACACS server")
        uut = self.parent.parameters['uut']
        commands = [
            f"tacacs server {uut.custom['tacacs_server_name']}",
            f" address ipv4 {uut.custom['tacacs_ip']}",
            " key cisco",
            " single-connection",
            " exit"
        ]
        try:
            uut.configure(commands)
        except Exception as e:
            logger.error(f"Failed to execute TACACS server configuration: {e}")
            self.failed("Failed to configure TACACS server")

    @aetest.test
    def configure_server_group(self):
        """Configure TACACS server group"""
        logger.info("Configuring TACACS server group")
        uut = self.parent.parameters['uut']
        commands = [
            f"aaa group server tacacs+ {uut.custom['tacacs_server_group']}",
            f" server name {uut.custom['tacacs_server_name']}",
            " exit"
        ]
        try:
            uut.configure(commands)
        except Exception as e:
            logger.error(f"Failed to execute server group configuration: {e}")
            self.failed("Failed to configure TACACS server group")

    @aetest.test
    def enable_accounting(self):
        """Enable accounting for privilege 15"""
        logger.info("Enabling accounting for privilege 15")
        uut = self.parent.parameters['uut']
        commands = [
            f"aaa authentication login default group {uut.custom['tacacs_server_group']} local",
            f"aaa authorization commands 15 default group {uut.custom['tacacs_server_group']} local",
            f"aaa accounting commands 15 default start-stop group {uut.custom['tacacs_server_group']}"
        ]
        try:
            uut.configure(commands)
        except Exception as e:
            logger.error(f"Failed to enable accounting: {e}")
            self.failed("Failed to enable accounting")

    @aetest.test
    def execute_privilege_15_cli(self):
        """Execute privilege 15 CLI"""
        logger.info("Executing privilege 15 CLI")
        uut = self.parent.parameters['uut']
        output = uut.execute("show running-config")
        logger.info(output)

    @aetest.test
    def verify_accounting_logs(self):
        """Verify accounting logs"""
        logger.info("Verifying accounting logs")
        uut = self.parent.parameters['uut']
        # Check TACACS server config
        output = uut.execute("show tacacs")
        if uut.custom['tacacs_server_name'] in output and uut.custom['tacacs_ip'] in output:
            logger.info("TACACS server is properly configured")
        else:
            logger.error("TACACS server configuration verification failed. Output:")
            logger.error(output)
            self.failed("TACACS server configuration verification failed")
        # Check for accounting logs
        logs = uut.execute("show logging | include accounting|TACACS|ksukulka|AAA")
        if "accounting" in logs or "TACACS" in logs or "AAA" in logs:
            self.passed("Accounting log found in device logs")
        else:
            logger.error("Accounting verification failed. No accounting record found for the command.")
            self.failed("Accounting verification failed")

    @aetest.test
    def verify_console_login(self):
        """Verify user accounting using console login"""
        logger.info("Verifying console login with TACACS")
        uut = self.parent.parameters['uut']
        output = uut.execute("show users")
        if "ksukulka" in output:
            self.passed("Console login verified successfully")
        else:
            self.failed("Console login verification failed")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from device"))
        uut = self.parent.parameters.get('uut')
        if uut and uut.connected:
            uut.disconnect()
