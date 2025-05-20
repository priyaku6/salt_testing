import logging
import re
import time
import socket
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut

        # Check for required custom keys
        required_custom_keys = [
            'tacacs_server_name',
            'tacacs_fqdn',
            'tacacs_server_group',
            'source_interface'
        ]
        missing_keys = [k for k in required_custom_keys if k not in uut.custom]
        if missing_keys:
            self.failed(f"Missing custom keys in testbed device definition: {missing_keys}")

        testscript.parameters['tacacs_server_name'] = uut.custom['tacacs_server_name']
        testscript.parameters['tacacs_fqdn'] = uut.custom['tacacs_fqdn']
        testscript.parameters['tacacs_server_group'] = uut.custom['tacacs_server_group']
        testscript.parameters['source_interface'] = uut.custom['source_interface']

        # Try to resolve FQDN to IP address
        try:
            tacacs_ip = socket.gethostbyname(uut.custom['tacacs_fqdn'])
            logger.info(f"Resolved {uut.custom['tacacs_fqdn']} to IP: {tacacs_ip}")
            testscript.parameters['tacacs_ip'] = tacacs_ip
        except Exception as e:
            logger.warning(f"Could not resolve {uut.custom['tacacs_fqdn']}: {str(e)}")
            testscript.parameters['tacacs_ip'] = "192.0.2.1"  # TEST-NET-1 placeholder

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        try:
            uut.connect()
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
        except Exception as e:
            self.failed(f"Connection failed: {str(e)}")

class TacacsFqdnAuthorizationTest(aetest.Testcase):
    @aetest.setup
    def setup(self, uut):
        logger.info("Enabling debugs for TACACS and SSL")
        uut.execute("debug aaa authentication")
        uut.execute("debug aaa authorization")
        uut.execute("debug tacacs")
        uut.execute("debug ip tcp transactions")
        uut.execute("debug crypto ssl")

    @aetest.test
    def configure_tacacs_server_fqdn(self, uut, tacacs_server_name, tacacs_fqdn, source_interface):
        logger.info(banner("Configuring TACACS server using FQDN"))
        config_cmds = [
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 {tacacs_fqdn}",
            f" key cisco"
        ]
        uut.configure(config_cmds)
        # Configure the global source interface
        uut.configure([f"ip tacacs source-interface {source_interface}"])
        logger.info("TACACS server with FQDN and global source-interface configured")

    @aetest.test
    def configure_server_group(self, uut, tacacs_server_group, tacacs_server_name):
        logger.info(banner("Configuring TACACS server group"))
        config_cmds = [
            f"aaa group server tacacs+ {tacacs_server_group}",
            f" server name {tacacs_server_name}"
        ]
        uut.configure(config_cmds)
        logger.info("TACACS server group configured")

    @aetest.test
    def enable_priv15_authorization(self, uut, tacacs_server_group):
        logger.info(banner("Enabling privilege 15 command authorization"))
        config_cmds = [
            f"aaa authorization commands 15 default group {tacacs_server_group} local",
            f"aaa authentication login default group {tacacs_server_group} local"
        ]
        uut.configure(config_cmds)
        logger.info("AAA authorization configured")

    @aetest.test
    def execute_priv15_command(self, uut):
        logger.info(banner("Executing privilege 15 command"))
        output = uut.execute("show running-config")
        logger.info(f"Command output:\n{output}")
        if "Current configuration" in output:
            logger.info("Privilege 15 command executed successfully")
        else:
            self.failed("Privilege 15 command failed or not authorized")

    @aetest.test
    def verify_authorization(self, uut):
        logger.info(banner("Verifying Authorization Success"))
        output = uut.execute("show logging | include AAA|TACACS|Authorization")
        logger.info(f"Authorization logs:\n{output}")
        if re.search(r'AUTHOR.*SUCCESS|Authorization succeeded', output, re.IGNORECASE):
            self.passed("Authorization was successful")
        else:
            self.failed("Authorization was not successful")

    @aetest.cleanup
    def cleanup_test(self, uut, tacacs_server_name, tacacs_server_group, source_interface):
        logger.info(banner("Cleaning up test configuration"))
        cleanup_cmds = [
            f"no aaa authorization commands 15 default",
            f"no aaa authentication login default",
            f"no aaa group server tacacs+ {tacacs_server_group}",
            f"no tacacs server {tacacs_server_name}",
            f"no ip tacacs source-interface {source_interface}"
        ]
        for cmd in cleanup_cmds:
            try:
                uut.configure(cmd)
            except Exception as e:
                logger.warning(f"Cleanup command failed: {cmd} - {str(e)}")
        # Disable debugs
        uut.execute("undebug all")
        logger.info("Cleanup complete. 'aaa new-model' and username configs are preserved.")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        try:
            uut.disconnect()
            logger.info("Device disconnected successfully")
        except Exception as e:
            logger.warning(f"Error disconnecting: {str(e)}")

if __name__ == "__main__":
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser(description="TACACS FQDN Authorization Test")
    parser.add_argument('--testbed', dest='testbed', type=loader.load, required=True)
    args, unknown = parser.parse_known_args()

    aetest.main(**vars(args))
