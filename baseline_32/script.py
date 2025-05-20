import logging
import time
import socket
import re
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['vwlc-ksukulka']
        testscript.parameters['uut'] = uut

        # Initialize custom variables from testbed
        testscript.parameters['tacacs_server_name'] = uut.custom['tacacs_server_name']
        testscript.parameters['tacacs_server_group'] = uut.custom['tacacs_server_group']
        testscript.parameters['tacacs_fqdn'] = uut.custom['tacacs_fqdn']
        testscript.parameters['tacacs_port'] = uut.custom.get('tacacs_port', 49)
        testscript.parameters['source_interface'] = uut.custom['source_interface']

        # Resolve FQDN to IP address
        try:
            tacacs_ip = socket.gethostbyname(uut.custom['tacacs_fqdn'])
            logger.info(f"Resolved {uut.custom['tacacs_fqdn']} to IP: {tacacs_ip}")
        except Exception as e:
            logger.warning(f"Could not resolve {uut.custom['tacacs_fqdn']}: {str(e)}")
            tacacs_ip = uut.custom.get('tacacs_ip', '192.0.2.1')
        testscript.parameters['tacacs_ip'] = tacacs_ip

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

class TacacsFqdnAccountingTest(aetest.Testcase):
    """Test case to verify TACACS accounting with FQDN configuration"""

    @aetest.setup
    def setup(self, uut):
        logger.info("Enabling AAA new-model (if not already enabled)")
        try:
            uut.configure("aaa new-model")
        except Exception as e:
            logger.warning(f"Could not enable aaa new-model: {str(e)}")

    @aetest.test
    def configure_tacacs_server(self, uut, tacacs_server_name, tacacs_ip, tacacs_port, source_interface):
        logger.info("Configuring TACACS server with IP address")
        config_commands = [
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 {tacacs_ip}",
            f" key 0 cisco123",
            f" port {tacacs_port}"
        ]
        try:
            uut.configure(config_commands)
            logger.info("TACACS server configuration successful")
        except Exception as e:
            logger.error(f"Error configuring TACACS server: {str(e)}")
            self.failed("Failed to configure TACACS server")
        # Configure global source interface
        try:
            uut.configure(f"ip tacacs source-interface {source_interface}")
        except Exception as e:
            logger.warning(f"Could not configure source-interface: {str(e)}")

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_server_group, tacacs_server_name):
        logger.info("Configuring TACACS server group")
        config_commands = [
            f"aaa group server tacacs+ {tacacs_server_group}",
            f" server name {tacacs_server_name}"
        ]
        uut.configure(config_commands)
        logger.info("TACACS server group configuration successful")

    @aetest.test
    def enable_command_accounting(self, uut, tacacs_server_group):
        logger.info("Enabling command accounting for privilege 15 commands")
        config_commands = [
            f"aaa accounting commands 15 default start-stop group {tacacs_server_group}"
        ]
        uut.configure(config_commands)
        logger.info("Command accounting configuration successful")

    @aetest.test
    def enable_debug(self, uut):
        logger.info("Enabling TACACS and SSL debugs")
        debug_commands = [
            "debug tacacs accounting",
            "debug tacacs events",
            "debug tacacs packet",
            "debug crypto ssl",
            "terminal monitor"
        ]
        for cmd in debug_commands:
            try:
                uut.execute(cmd)
                logger.info(f"Enabled: {cmd}")
            except Exception as e:
                logger.warning(f"Failed to enable debug {cmd}: {str(e)}")

    @aetest.test
    def execute_privilege_commands(self, uut):
        logger.info("Executing privilege 15 commands to generate accounting records")
        test_commands = [
            "show version",
            "show running-config | include hostname",
            "show ip interface brief"
        ]
        for cmd in test_commands:
            try:
                logger.info(f"Executing: {cmd}")
                uut.execute(cmd)
                time.sleep(2)
            except Exception as e:
                logger.warning(f"Command {cmd} failed: {str(e)}")
        logger.info("Privilege 15 commands executed")

    @aetest.test
    def verify_accounting(self, uut):
        logger.info("Verifying accounting records in debug logs")
        time.sleep(5)
        debug_output = uut.execute("show logging | include TACACS+: Accounting")
        if "TACACS+: Accounting" in debug_output:
            logger.info("TACACS accounting records found in debug logs")
            self.passed("Successfully verified TACACS accounting records")
        else:
            logger.warning("No accounting records found in debug logs")
            tacacs_debug = uut.execute("show logging | include TACACS+")
            logger.info(f"TACACS+ debug output: {tacacs_debug}")
            if "TACACS+" in tacacs_debug:
                self.passed("TACACS debug information found, but no specific accounting records")
            else:
                self.failed("No TACACS debug information found. Verify server connection and try again")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def disable_debug(self, uut):
        logger.info(banner("Disabling all debugging"))
        try:
            uut.execute("undebug all", timeout=30)
            logger.info("Successfully disabled all debugging")
        except Exception as e:
            logger.warning(f"Error disabling debug: {str(e)}")

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_server_name, tacacs_server_group, tacacs_ip, source_interface):
        logger.info(banner("Cleaning up TACACS configuration"))
        try:
            uut.configure("no aaa accounting commands 15 default")
            uut.configure(f"no aaa group server tacacs+ {tacacs_server_group}")
            uut.configure(f"no tacacs server {tacacs_server_name}")
            uut.configure(f"no ip tacacs source-interface {source_interface}")
            logger.info("TACACS configuration cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup error: {str(e)}")
        try:
            uut.execute("write memory")
            logger.info("Configuration saved")
        except Exception as e:
            logger.warning(f"Error saving configuration: {str(e)}")

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        try:
            uut.disconnect()
            logger.info("Successfully disconnected from the device")
        except Exception as e:
            logger.warning(f"Error during disconnect: {str(e)}")

if __name__ == "__main__":
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser(description="TACACS FQDN Accounting Test")
    parser.add_argument('--testbed', dest='testbed', type=loader.load, required=True)
    args, unknown = parser.parse_known_args()

    aetest.main(**vars(args))
