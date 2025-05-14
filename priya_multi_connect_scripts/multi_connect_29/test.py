# Full script for configuring TACACS servers using legacy commands.

import logging
from pyats import aetest

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']  # Ensure the device name matches the testbed YAML
        try:
            self.device.connect(via='a')  # Use 'a' as defined in the testbed YAML
        except Exception as e:
            self.failed(f"Failed to connect to device: {e}")

    @aetest.subsection
    def enable_debug(self):
        """Enable required debugs"""
        try:
            debug_commands = [
                "terminal prc expose",
                "debug tacacs accounting",
                "debug tacacs events",
                "debug tacacs packet"
            ]
            for cmd in debug_commands:
                self.device.execute(cmd)
        except Exception as e:
            self.failed(f"Failed to enable debug: {e}")

class TacacsTest(aetest.Testcase):
    @aetest.setup
    def setup(self, testbed):
        """Configure AAA new-model"""
        self.device = testbed.devices['vwlc-ksukulka']
        try:
            self.device.configure("aaa new-model")
        except Exception as e:
            self.failed(f"Failed to configure AAA new-model: {e}")
        
    @aetest.test
    def configure_nontls_servers(self):
        """Configure non-TLS TACACS servers"""
        try:
            config = f"""
            tacacs-server host {self.device.custom['nontls_server1_ip']}
            tacacs-server key {self.device.custom['tacacs_key']}
            tacacs-server host {self.device.custom['nontls_server2_ip']}
            tacacs-server key {self.device.custom['tacacs_key']}
            """
            self.device.configure(config)
        except Exception as e:
            self.failed(f"Failed to configure non-TLS servers: {e}")

    @aetest.test
    def configure_server_groups(self):
        """Configure TACACS server groups"""
        try:
            config = """
            aaa group server tacacs+ NonTLS_Group
             server name NonTLS_Server1
            !
            aaa group server tacacs+ TLS_Group
             server name TLS_Server1
            """
            self.device.configure(config)
        except Exception as e:
            self.failed(f"Failed to configure server groups: {e}")

    @aetest.test
    def configure_aaa_accounting(self):
        """Configure AAA accounting"""
        try:
            config = """
            aaa authentication login default group tacacs+ local
            aaa accounting commands 15 default start-stop group tacacs+
            """
            self.device.configure(config)
        except Exception as e:
            self.failed(f"Failed to configure AAA accounting: {e}")

    @aetest.test
    def verify(self):
        """Verify TACACS configuration"""
        try:
            # Verify TACACS configuration
            output = self.device.execute("show running-config | include tacacs")
            if "tacacs-server" not in output:
                self.failed("TACACS configuration is missing")
            
            # Verify TACACS logs
            logs = self.device.execute("show logging | include TACACS")
            if "TACACS" not in logs:
                self.failed("No TACACS logs found")
        except Exception as e:
            self.failed(f"Failed to verify TACACS configuration: {e}")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disable_debug(self, testbed):
        """Disable all debugs"""
        self.device = testbed.devices['vwlc-ksukulka']
        try:
            debug_commands = [
                "no debug all",
                "terminal prc hide"
            ]
            for cmd in debug_commands:
                self.device.execute(cmd)
        except Exception as e:
            self.failed(f"Failed to disable debug: {e}")

    @aetest.subsection
    def cleanup_config(self, testbed):
        """Remove test configurations"""
        self.device = testbed.devices['vwlc-ksukulka']
        try:
            config = f"""
            no aaa accounting commands 15 default
            no aaa authentication login default
            no tacacs-server host {self.device.custom['nontls_server1_ip']}
            no tacacs-server host {self.device.custom['nontls_server2_ip']}
            """
            self.device.configure(config)
        except Exception as e:
            self.failed(f"Failed to clean up configuration: {e}")

    @aetest.subsection
    def disconnect(self, testbed):
        """Disconnect from the device"""
        self.device = testbed.devices['vwlc-ksukulka']
        try:
            self.device.disconnect()
        except Exception as e:
            self.failed(f"Failed to disconnect from device: {e}")
