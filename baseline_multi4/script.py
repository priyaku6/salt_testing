import logging
import time
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['vwlc-ksukulka']
        testscript.parameters['uut'] = uut
        testscript.parameters['tacacs_server1_name'] = uut.custom['tacacs_server1_name']
        testscript.parameters['tacacs_server1_ip'] = uut.custom['tacacs_server1_ip']
        testscript.parameters['tacacs_server2_name'] = uut.custom['tacacs_server2_name']
        testscript.parameters['tacacs_server2_ip'] = uut.custom['tacacs_server2_ip']
        testscript.parameters['tacacs_key'] = uut.custom['tacacs_key']
        testscript.parameters['tacacs_group'] = uut.custom['tacacs_group']
        testscript.parameters['source_interface'] = uut.custom['source_interface']

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device via SSH..."))
        uut.connect(via='ssh')
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

class TacacsMultiServerAuthTest(aetest.Testcase):
    @aetest.setup
    def setup(self, uut):
        logger.info("Enabling AAA new-model")
        uut.configure(["aaa new-model"])
        output = uut.execute("show running-config | include aaa new-model")
        if "aaa new-model" not in output:
            self.failed("Failed to enable AAA new-model")
        logger.info("AAA new-model enabled successfully")

    @aetest.test
    def configure_tacacs_servers(self, uut, tacacs_server1_name, tacacs_server1_ip, tacacs_server2_name, tacacs_server2_ip, tacacs_key, source_interface):
        logger.info(banner("Configuring two TACACS servers"))
        tacacs_commands = [
            f"tacacs server {tacacs_server1_name}",
            f" address ipv4 {tacacs_server1_ip}",
            f" key {tacacs_key}",
            "exit",
            f"tacacs server {tacacs_server2_name}",
            f" address ipv4 {tacacs_server2_ip}",
            f" key {tacacs_key}",
            "exit",
            f"ip tacacs source-interface {source_interface}"
        ]
        uut.configure(tacacs_commands)
        logger.info("Both TACACS servers configured successfully")

    @aetest.test
    def configure_tacacs_server_group(self, uut, tacacs_server1_name, tacacs_server2_name, tacacs_group):
        logger.info(banner("Configuring TACACS server group with both servers (non-working first)"))
        commands = [
            f"aaa group server tacacs+ {tacacs_group}",
            f" server name {tacacs_server1_name}",
            f" server name {tacacs_server2_name}",
            "exit"
        ]
        uut.configure(commands)
        logger.info("TACACS server group configured successfully")

    @aetest.test
    def enable_login_authentication(self, uut, tacacs_group):
        logger.info(banner("Enabling login authentication"))
        commands = [
            f"aaa authentication login default group {tacacs_group} local"
        ]
        uut.configure(commands)
        logger.info("Login authentication configured successfully")
        time.sleep(3)

    @aetest.test
    def verify_ssh_login(self, uut):
        logger.info(banner("Verifying SSH login with TACACS authentication"))
        # Disconnect and reconnect to simulate a new SSH login
        uut.disconnect()
        time.sleep(2)
        uut.connect(via='ssh')
        assert uut.connected, "SSH login failed"
        logger.info("SSH login with TACACS authentication successful")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup_config(self, uut, tacacs_server1_name, tacacs_server2_name, tacacs_group, source_interface):
        logger.info(banner("Cleaning up TACACS configuration"))
        uut.configure([
            "no aaa authentication login default",
            f"no aaa group server tacacs+ {tacacs_group}",
            f"no tacacs server {tacacs_server1_name}",
            f"no tacacs server {tacacs_server2_name}",
            f"no ip tacacs source-interface {source_interface}"
        ])
        uut.execute("write memory")
        logger.info("TACACS configuration cleaned up successfully")

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()

if __name__ == '__main__':
    import argparse
    from pyats.topology import loader
    parser = argparse.ArgumentParser(description="TACACS Multi-Server SSH Authentication Test")
    parser.add_argument('--testbed', dest='testbed', type=loader.load, required=True)
    args, unknown = parser.parse_known_args()
    aetest.main(**vars(args))
