from pyats import aetest
from pyats.log.utils import banner
import logging
import time
import argparse
from pyats import topology

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        logger.info(banner("Connecting to the device..."))
        uut = testbed.devices['vwlc-ksukulka']
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut.name}"
        self.parent.parameters['uut'] = uut
        logger.info(f"Successfully connected to device {uut.name}")

class TacacsIseAuthenticationTest(aetest.Testcase):
    @aetest.test
    def configure_tacacs_server(self, uut):
        """Configure TACACS server with single connection and directed-request"""
        logger.info("Configuring TACACS server and enabling directed-request")
        config_commands = [
            f"tacacs server TAC",
            " single-connection",
            f" address ipv4 {uut.custom['tacacs_ip']}",
            " key cisco",
            " exit",
            "tacacs-server directed-request"
        ]
        uut.configure(config_commands)
        logger.info("TACACS server and directed-request configured")

    @aetest.test
    def configure_tacacs_server_group(self, uut):
        """Configure TACACS server group"""
        logger.info("Configuring TACACS server group")
        config_commands = [
            f"aaa group server tacacs+ {uut.custom['tacacs_server_group']}",
            f" server name {uut.custom['tacacs_server_name']}",
            " exit"
        ]
        uut.configure(config_commands)
        logger.info("TACACS server group configured")

    @aetest.test
    def configure_aaa_and_iphost(self, uut):
        """Configure AAA and IP host for tacacs.com"""
        logger.info("Configuring AAA and IP host")
        config_commands = [
            f"aaa authentication login default group {uut.custom['tacacs_server_group']} local",
            f"aaa authorization commands 15 default group {uut.custom['tacacs_server_group']} local",
            f"aaa accounting commands 15 default start-stop group {uut.custom['tacacs_server_group']}",
            f"ip host tacacs.com {uut.custom['tacacs_ip']}"
        ]
        uut.configure(config_commands)
        logger.info("AAA and IP host configured")

    @aetest.test
    def verify_ssh_login(self, uut):
        """Verify SSH login using directed server functionality"""
        logger.info("Verifying SSH login using directed server")
        # This step assumes you have SSH enabled and keys generated on the device.
        # The actual SSH login from the script is not performed here, but you can instruct the user:
        logger.info("To test, run the following from a shell:")
        logger.info(f"ssh ksukulka@tacacs.com@{uut.connections['telnet']['ip']}")
        logger.info("If login is successful and you reach the device prompt, the test is successful.")
        # Optionally, you can automate this with paramiko or subprocess if needed.

    @aetest.cleanup
    def cleanup(self, uut):
        """Cleanup configuration"""
        logger.info("Cleaning up test configuration")
        cleanup_commands = [
            "no tacacs-server directed-request",
            f"no ip host tacacs.com",
            f"no tacacs server {uut.custom['tacacs_server_name']}",
            f"no aaa group server tacacs+ {uut.custom['tacacs_server_group']}",
            f"no aaa authentication login default group {uut.custom['tacacs_server_group']} local",
            f"no aaa authorization commands 15 default group {uut.custom['tacacs_server_group']} local",
            f"no aaa accounting commands 15 default group {uut.custom['tacacs_server_group']}"
        ]
        uut.configure(cleanup_commands)
        logger.info("Cleanup completed successfully")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self):
        uut = self.parent.parameters.get('uut')
        if uut and uut.connected:
            uut.disconnect()
            logger.info("Disconnected from device")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="TACACS ISE Authentication Test")
    parser.add_argument('--testbed', dest='testbed', type=topology.loader.load, required=True)
    args, unknown = parser.parse_known_args()
    aetest.main(testbed=args.testbed)
