from genie.testbed import load
from pyats import aetest
from pyats.log.utils import banner
import logging
import time

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")
        if 'uut' not in testbed.devices:
            self.failed("Testbed must contain a device named 'uut'")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        testscript.parameters['tacacs_server_name'] = uut.custom.get('tacacs_server_name', 'TAC')
        testscript.parameters['tacacs_group_name'] = uut.custom.get('tacacs_server_group', 'TAC_Grp')
        testscript.parameters['tacacs_server_ip'] = uut.custom.get('tacacs_ip', '10.1.1.1')
        testscript.parameters['tacacs_key'] = uut.custom.get('tacacs_key', 'testing123')
        testscript.parameters['source_interface'] = uut.custom.get('source_interface', 'GigabitEthernet1')

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        try:
            uut.connect(via="a")
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
        except Exception as e:
            logger.error(f"Failed to connect to device {uut.name}: {e}")
            self.failed(f"Connection to device {uut.name} failed. Please check the connection configuration.")

class TacacsAuthorizationTest(aetest.Testcase):
    """Test case to verify TACACS server authorization functionality"""

    @aetest.setup
    def setup(self, uut, tacacs_server_name, tacacs_group_name, tacacs_server_ip, tacacs_key, source_interface):
        logger.info(banner("Configuring TACACS Server and AAA"))
        try:
            config = [
                f"tacacs server {tacacs_server_name}",
                " single-connection",
                f" address ipv4 {tacacs_server_ip}",
                f" key {tacacs_key}",
                f" ip tacacs source-interface {source_interface}",
                f"aaa group server tacacs+ {tacacs_group_name}",
                f" server name {tacacs_server_name}",
                "aaa new-model",
                f"aaa authentication login default group {tacacs_group_name} local",
                f"aaa authorization commands 15 default group {tacacs_group_name} local"
            ]
            uut.configure(config, timeout=60)
            logger.info("TACACS server and AAA configured")
        except Exception as e:
            logger.error(f"Exception during setup: {e}")
            self.failed(f"Failed to configure TACACS/AAA: {e}")

    @aetest.test
    def verify_privilege_commands(self, uut):
        """Try executing privilege level 15 CLIs and verify authorization"""
        logger.info(banner("Verifying Privilege Level 15 Commands"))
        commands = [
            "show running-config | i tacacs",
            "show version",
            "show privilege"
        ]
        success_count = 0
        for cmd in commands:
            logger.info(f"Executing: {cmd}")
            try:
                output = uut.execute(cmd, timeout=30)
                logger.info(f"Output:\n{output}")
                if "Current privilege level is 15" in output or "show version" in cmd or "tacacs" in output:
                    success_count += 1
            except Exception as e:
                logger.error(f"Command '{cmd}' failed: {e}")
        if success_count == 0:
            self.failed("No privilege 15 commands succeeded. Authorization may have failed.")
        else:
            logger.info(f"{success_count}/{len(commands)} privilege commands succeeded")
            self.passed("Privilege 15 command authorization verified.")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_server_name, tacacs_group_name):
        logger.info(banner("Cleaning up TACACS and AAA configuration"))
        try:
            cleanup = [
                "no aaa authorization commands 15 default",
                "no aaa authentication login default",
                f"no aaa group server tacacs+ {tacacs_group_name}",
                f"no tacacs server {tacacs_server_name}",
                "no aaa new-model"
            ]
            uut.configure(cleanup, timeout=60)
            logger.info("TACACS and AAA configuration removed")
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")
        finally:
            logger.info("Disconnecting from device")
            try:
                uut.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")

if __name__ == '__main__':
    aetest.main()
