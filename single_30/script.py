import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']  # Replace with the correct device name
        self.device.connect(via='ssh')  # Connect using SSH
        self.parent.parameters['device'] = self.device  # Pass the device to test cases
        logger.info(f"Connected to device: {self.device.name}")

class TacacsServerConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug aaa authentication",
            "debug aaa authorization",
            "debug tacacs events",
            "debug tacacs authentication",
            "debug ssl errors"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_server(self, device):
        """Configure TACACS+ server with FQDN and TLS"""
        try:
            config_commands = [
                f"tacacs server {device.custom['tacacs_server_name']}",
                f" address {device.custom['address_type']} {device.custom['tacacs_fqdn']}",
                " tls",
                f" tls port {device.custom['tls_port']}",
                f" tls idle-timeout {device.custom['idle_timeout']}",
                f" tls connection-timeout {device.custom['connection_timeout']}",
                f" ip tacacs source-interface {device.custom['source_interface']}"
            ]
            device.configure(config_commands)
            logger.info("TACACS+ server configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def configure_server_group(self, device):
        """Configure TACACS+ server group"""
        try:
            config_commands = [
                f"aaa group server tacacs+ {device.custom['server_group']}",
                f" server name {device.custom['tacacs_server_name']}"
            ]
            device.configure(config_commands)
            logger.info("TACACS+ server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server group: {str(e)}")

    @aetest.test
    def configure_login_authentication(self, device):
        """Configure login authentication using the TACACS+ server group"""
        try:
            config_commands = [
                "aaa new-model",
                f"aaa authentication login default group {device.custom['server_group']} local"
            ]
            device.configure(config_commands)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def perform_ssh_login(self, device):
        """Perform SSH login to the device and verify success"""
        try:
            # Disconnect current session
            device.disconnect()
            # Reconnect via SSH
            device.connect(via='ssh')
            # Verify connection
            output = device.execute("show users")
            if "*" in output:
                logger.info("SSH login successful.")
            else:
                self.failed("SSH login verification failed.")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            f"no tacacs server {device.custom['tacacs_server_name']}",
            f"no aaa group server tacacs+ {device.custom['server_group']}",
            "no aaa authentication login default",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")

if __name__ == "__main__":
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser(description="TACACS+ TLS Test Script")
    parser.add_argument('--testbed', required=True, help="Path to the testbed file")
    args = parser.parse_args()

    # Load the testbed and run the test
    testbed = loader.load(args.testbed)
    aetest.main(testbed=testbed)
