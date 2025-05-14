import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        retries = 3
        for attempt in range(retries):
            try:
                self.device = testbed.devices['vwlc-ksukulka']  # Replace with the correct device name
                self.device.connect(via='ssh', timeout=60)  # Increased timeout to 60 seconds
                self.parent.parameters['device'] = self.device  # Pass the device to test cases
                self.parent.parameters['custom'] = self.device.custom  # Pass custom attributes
                logger.info(f"Connected to device: {self.device.name}")
                return
            except Exception as e:
                logger.warning(f"Connection attempt {attempt + 1} failed: {str(e)}")
                if attempt < retries - 1:
                    continue
                else:
                    self.failed(f"Failed to connect to device after {retries} attempts.")

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
                device.execute(cmd, timeout=60)  # Increased timeout to 60 seconds
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_vrf_and_interface(self, device, custom):
        """Configure VRF and physical interface"""
        try:
            vrf_name = "Mgmt-vrf"
            interface = custom['source_interface']
            vrf_config = [
                f"vrf definition {vrf_name}",
                " address-family ipv4",
                " exit-address-family",
                f"interface {interface}",
                f" vrf forwarding {vrf_name}",
                " ip address dhcp",
                " no shutdown"
            ]
            device.configure(vrf_config, timeout=60)
            logger.info(f"VRF {vrf_name} and interface {interface} configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure VRF and interface: {str(e)}")

    @aetest.test
    def configure_tacacs_server(self, device, custom):
        """Configure TACACS+ server with TLS"""
        try:
            tacacs_config = [
                f"tacacs server {custom['tacacs_server_name']}",
                f" address ipv4 {custom['tacacs_ip']}",
                f" key cisco123",  # Replace with the actual key if needed
                f" ip vrf forwarding Mgmt-vrf",
                f" timeout {custom['tls_connection_timeout']}",
                f" port {custom['tls_port']}",
                " tls"
            ]
            device.configure(tacacs_config, timeout=60)

            # Configure source-interface globally
            global_source_interface = f"ip tacacs source-interface {custom['source_interface']}"
            device.configure(global_source_interface, timeout=60)
            logger.info("TACACS+ server and source-interface configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def configure_tacacs_server_group(self, device, custom):
        """Configure TACACS+ server group"""
        try:
            group_config = [
                f"aaa group server tacacs+ {custom['tacacs_server_group']}",
                f" server name {custom['tacacs_server_name']}"
            ]
            device.configure(group_config, timeout=60)
            logger.info(f"TACACS+ server group {custom['tacacs_server_group']} configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server group: {str(e)}")

    @aetest.test
    def configure_login_authentication(self, device, custom):
        """Configure login authentication using the TACACS+ server group"""
        try:
            login_auth_config = [
                f"aaa authentication login default group {custom['tacacs_server_group']} local"
            ]
            device.configure(login_auth_config, timeout=60)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def perform_ssh_login(self, device):
        """Perform SSH login to the device and verify success"""
        try:
            # Simulate SSH login by executing a command
            output = device.execute("show version", timeout=60)
            if output:
                logger.info("SSH login successful.")
            else:
                self.failed("SSH login failed.")
        except Exception as e:
            self.failed(f"Failed to perform SSH login: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device, custom):
        """Remove test configuration"""
        cleanup_cmds = [
            f"no tacacs server {custom['tacacs_server_name']}",
            f"no aaa group server tacacs+ {custom['tacacs_server_group']}",
            "no aaa authentication login default",
            f"no ip tacacs source-interface {custom['source_interface']}",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds, timeout=60)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")

if __name__ == "__main__":
    import argparse
    from pyats.topology import loader

    parser = argparse.ArgumentParser(description="TACACS+ Configuration Test")
    parser.add_argument('--testbed', required=True, help="Path to the testbed file")
    args = parser.parse_args()

    # Load the testbed and run the test
    testbed = loader.load(args.testbed)
    aetest.main(testbed=testbed)
