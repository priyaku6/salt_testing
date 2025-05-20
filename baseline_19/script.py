from pyats import aetest
from pyats.log.utils import banner
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_device(self, testbed):
        logger.info(banner("Connecting to the device via telnet"))
        uut = testbed.devices['uut']
        uut.connect(via='telnet')
        assert uut.connected, "Failed to connect to the device via telnet"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    @aetest.test
    def enable_tacacs(self):
        logger.info("Configuring ISE to enable TACACS (manual/external step)")
        # Add ISE configuration steps here if needed

class TacacsConfigurationTest(aetest.Testcase):
    @aetest.test
    def configure_tacacs_servers(self, uut):
        logger.info("Configuring TACACS servers and groups")
        try:
            commands = [
                f"tacacs server {uut.custom['tacacs_nonworking_name']}",
                f" address ipv4 {uut.custom['tacacs_nonworking_ip']}",
                " port 49",
                "!",
                f"tacacs server {uut.custom['tacacs_working_name']}",
                f" address ipv4 {uut.custom['tacacs_working_ip']}",
                " port 49",
                "!",
                f"aaa group server tacacs+ {uut.custom['tacacs_nonworking_group']}",
                f" server name {uut.custom['tacacs_nonworking_name']}",
                "!",
                f"aaa group server tacacs+ {uut.custom['tacacs_working_group']}",
                f" server name {uut.custom['tacacs_working_name']}",
                "!"
            ]
            uut.configure(commands)
            logger.info("TACACS servers and groups configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure TACACS servers/groups: {e}")
            self.failed(f"Failed to configure TACACS servers/groups: {e}")

    @aetest.test
    def enable_authorization_nonworking(self, uut):
        logger.info("Enabling authorization with NONWORKING group")
        try:
            commands = [
                f"aaa authentication login default group {uut.custom['tacacs_nonworking_group']} local",
                f"aaa authorization commands 15 default group {uut.custom['tacacs_nonworking_group']} local"
            ]
            uut.configure(commands)
            logger.info("Authorization enabled with NONWORKING group")
        except Exception as e:
            logger.error(f"Failed to enable authorization: {e}")
            self.failed(f"Failed to enable authorization: {e}")

    @aetest.test
    def verify_authorization_nonworking(self, uut):
        logger.info("Verifying authorization with NONWORKING group")
        try:
            output = uut.execute("show running-config")
            logger.debug(f"Authorization verification output:\n{output}")
            expected = f"aaa authorization commands 15 default group {uut.custom['tacacs_nonworking_group']} local"
            if expected in output:
                logger.info("Authorization config present (NONWORKING group)")
            else:
                logger.error("Authorization verification failed. Expected configuration not found.")
                self.failed("Authorization verification failed (NONWORKING group)")
        except Exception as e:
            logger.error(f"Failed to verify authorization: {e}")
            self.failed(f"Failed to verify authorization: {e}")

    @aetest.test
    def enable_authorization_working(self, uut):
        logger.info("Enabling authorization with WORKING group")
        try:
            commands = [
                f"aaa authentication login default group {uut.custom['tacacs_working_group']} local",
                f"aaa authorization commands 15 default group {uut.custom['tacacs_working_group']} local"
            ]
            uut.configure(commands)
            logger.info("Authorization enabled with WORKING group")
        except Exception as e:
            logger.error(f"Failed to enable authorization: {e}")
            self.failed(f"Failed to enable authorization: {e}")

    @aetest.test
    def verify_authorization_working(self, uut):
        logger.info("Verifying authorization with WORKING group")
        try:
            output = uut.execute("show running-config")
            logger.debug(f"Authorization verification output:\n{output}")
            expected = f"aaa authorization commands 15 default group {uut.custom['tacacs_working_group']} local"
            if expected in output:
                logger.info("Authorization config present (WORKING group)")
                self.passed("Authorization verified successfully (WORKING group)")
            else:
                logger.error("Authorization verification failed. Expected configuration not found.")
                self.failed("Authorization verification failed (WORKING group)")
        except Exception as e:
            logger.error(f"Failed to verify authorization: {e}")
            self.failed(f"Failed to verify authorization: {e}")

class PrivilegeCommandTest(aetest.Testcase):
    @aetest.test
    def execute_privilege_command(self, uut):
        logger.info("Executing privilege level 15 command on telnet console")
        try:
            output = uut.execute("show running-config")
            logger.debug(f"Privilege command output:\n{output}")
            if "Current configuration" in output:
                self.passed("Privilege 15 command executed successfully")
            else:
                logger.error("Privilege 15 command failed or not authorized")
                self.failed("Privilege 15 command failed or not authorized")
        except Exception as e:
            logger.error(f"Failed to execute privilege command: {e}")
            self.failed(f"Failed to execute privilege command: {e}")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup_config(self, uut=None):
        logger.info(banner("Cleaning up TACACS configuration"))
        if not uut:
            uut = self.parent.parameters.get('uut')
            if not uut:
                self.failed("Device 'uut' is not available for cleanup")
        try:
            commands = [
                f"no tacacs server {uut.custom['tacacs_nonworking_name']}",
                f"no tacacs server {uut.custom['tacacs_working_name']}",
                f"no aaa group server tacacs+ {uut.custom['tacacs_nonworking_group']}",
                f"no aaa group server tacacs+ {uut.custom['tacacs_working_group']}",
                f"no aaa authentication login default group {uut.custom['tacacs_nonworking_group']} local",
                f"no aaa authentication login default group {uut.custom['tacacs_working_group']} local",
                f"no aaa authorization commands 15 default group {uut.custom['tacacs_nonworking_group']} local",
                f"no aaa authorization commands 15 default group {uut.custom['tacacs_working_group']} local"
            ]
            uut.configure(commands)
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            self.failed(f"Cleanup failed: {e}")
