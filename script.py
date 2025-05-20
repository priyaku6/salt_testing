import logging
import re
import time
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

DEVICE_NAME = 'vwlc-ksukulka'  # Change this if your device name changes

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices[DEVICE_NAME]
        testscript.parameters['uut'] = uut
        required_keys = [
            'tacacs_server_name', 'tacacs_server_group', 'tacacs_fqdn', 'tacacs_ip',
            'tls_port', 'tls_idle_timeout', 'tls_connection_timeout', 'tls_retries',
            'source_interface', 'priv_level'
        ]
        for key in required_keys:
            if key not in uut.custom:
                raise Exception(f"Device custom section missing required key: '{key}'")
        testscript.parameters['tacacs_server_name'] = uut.custom['tacacs_server_name']
        testscript.parameters['tacacs_server_group'] = uut.custom['tacacs_server_group']
        testscript.parameters['tacacs_fqdn'] = uut.custom['tacacs_fqdn']
        testscript.parameters['tacacs_ip'] = uut.custom['tacacs_ip']
        testscript.parameters['tls_port'] = uut.custom['tls_port']
        testscript.parameters['tls_idle_timeout'] = uut.custom['tls_idle_timeout']
        testscript.parameters['tls_connection_timeout'] = uut.custom['tls_connection_timeout']
        testscript.parameters['tls_retries'] = uut.custom['tls_retries']
        testscript.parameters['source_interface'] = uut.custom['source_interface']
        testscript.parameters['priv_level'] = uut.custom['priv_level']
        testscript.parameters['tacacs_key'] = uut.custom.get('tacacs_key', 'cisco123')

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

class TacacsSingleServerTest(aetest.Testcase):
    def safe_execute(self, uut, command, timeout=30, error_msg="Command failed"):
        try:
            output = uut.execute(command, timeout=timeout)
            return output
        except Exception as e:
            logger.warning(f"{error_msg}: {str(e)}")
            return f"ERROR: {str(e)}"

    def safe_configure(self, uut, commands, timeout=30, error_msg="Configuration failed"):
        if isinstance(commands, str):
            commands = [commands]
        results = []
        try:
            for cmd in commands:
                try:
                    result = uut.configure(cmd, timeout=timeout)
                    results.append(result)
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Error with command '{cmd}': {str(e)}")
                    results.append(f"ERROR: {str(e)}")
            return results
        except Exception as e:
            logger.warning(f"{error_msg}: {str(e)}")
            return [f"ERROR: {str(e)}"]

    @aetest.setup
    def setup(self, uut):
        logger.info("Enabling AAA new-model and debugs")
        self.safe_configure(uut, "aaa new-model")
        self.safe_execute(uut, "debug aaa authentication")
        self.safe_execute(uut, "debug aaa authorization")
        self.safe_execute(uut, "debug tacacs")
        self.safe_execute(uut, "debug ip tcp transactions")
        self.safe_execute(uut, "debug crypto ssl")

    @aetest.test
    def configure_tacacs_server_and_group(self, uut, tacacs_server_name, tacacs_fqdn, tacacs_key, tls_port,
                                          tls_idle_timeout, tls_connection_timeout, tls_retries, source_interface,
                                          tacacs_server_group):
        logger.info(banner("Configuring TACACS+ server and group"))
        cleanup = [
            f"no tacacs server {tacacs_server_name}",
            f"no aaa group server tacacs+ {tacacs_server_group}"
        ]
        self.safe_configure(uut, cleanup)
        config = [
            f"tacacs server {tacacs_server_name}",
            f" address ipv4 {tacacs_fqdn}",
            f" key {tacacs_key}",
            f" port {tls_port}",
            f" timeout {tls_connection_timeout}",
            f" retransmit {tls_retries}",
            f" source-interface {source_interface}",
            " exit",
            f"aaa group server tacacs+ {tacacs_server_group}",
            f" server name {tacacs_server_name}",
            " exit"
        ]
        self.safe_configure(uut, config)
        logger.info("TACACS+ server and group configured.")

    @aetest.test
    def configure_aaa_authorization(self, uut, tacacs_server_group, priv_level):
        logger.info(banner("Configuring AAA authorization for privilege level"))
        config = [
            f"aaa authentication login default group {tacacs_server_group} local",
            f"aaa authorization commands {priv_level} default group {tacacs_server_group} local"
        ]
        self.safe_configure(uut, config)
        logger.info("AAA authorization configured.")

    @aetest.test
    def verify_authorization(self, uut):
        logger.info(banner("Verifying privilege command authorization via SSH"))
        output = self.safe_execute(uut, "show running-config | include hostname")
        logger.info(f"Privilege command output: {output}")
        debug_out = self.safe_execute(uut, "show logging | include AUTH|TACACS|Authorization|PASS_ADD")
        logger.info(f"Relevant debug logs:\n{debug_out}")
        if re.search(r'Authorization.*granted|AUTH.*ACCEPT|Post authorization status = PASS_ADD', debug_out, re.IGNORECASE):
            self.passed("Authorization was successful (log verified)")
        else:
            self.failed("Authorization not verified in debug logs")

    @aetest.cleanup
    def cleanup_test(self, uut, tacacs_server_name, tacacs_server_group):
        logger.info(banner("Cleaning up test configuration"))
        cleanup = [
            "no aaa authorization commands 15 default",
            "no aaa authentication login default",
            f"no aaa group server tacacs+ {tacacs_server_group}",
            f"no tacacs server {tacacs_server_name}"
        ]
        self.safe_configure(uut, cleanup)
        self.safe_execute(uut, "undebug all")
        self.safe_configure(uut, "no aaa new-model")
        self.safe_execute(uut, "write memory")
        logger.info("Cleanup complete.")

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
    parser = argparse.ArgumentParser(description="TACACS+ Single-Server Test")
    parser.add_argument('--testbed', dest='testbed', type=loader.load, required=True)
    args, unknown = parser.parse_known_args()
    aetest.main(**vars(args))
