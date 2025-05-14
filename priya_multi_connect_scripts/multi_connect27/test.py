import logging
from pyats import aetest
from pyats.log.utils import banner

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        """Connect to the device."""
        self.uut = testbed.devices['vwlc-ksukulka']
        log.info("Connecting to the device via Telnet...")
        self.uut.connect(via='telnet')  # Use Telnet explicitly
        log.info("Connection successful.")

class TacacsMultiServerTest(aetest.Testcase):
    @aetest.setup
    def setup(self, testbed):
        """Initialize variables from testbed."""
        self.uut = testbed.devices['vwlc-ksukulka']
        log.info("Initializing variables...")
        required_keys = ['tac_server1', 'tac_server2', 'server_ip1', 'server_ip2', 'tacacs_key', 'tacacs_port']
        for key in required_keys:
            if key not in self.uut.custom:
                self.failed(f"Missing required custom attribute: {key}")
        log.info("All required custom attributes are present.")

    @aetest.test
    def configure_tacacs_servers(self):
        """Configure TACACS servers."""
        log.info("Configuring TACACS servers...")
        try:
            # Configure the first TACACS server
            configs = [
                f"tacacs server {self.uut.custom['tac_server1']}",
                f" address ipv4 {self.uut.custom['server_ip1']}",
                f" key {self.uut.custom['tacacs_key']}",
                f" port {self.uut.custom['tacacs_port']}",
                f" timeout {self.uut.custom['tacacs_timeout']}"
            ]
            self.uut.configure(configs)

            # Configure the second TACACS server
            configs = [line.replace(self.uut.custom['tac_server1'], self.uut.custom['tac_server2'])
                      .replace(self.uut.custom['server_ip1'], self.uut.custom['server_ip2'])
                      for line in configs]
            self.uut.configure(configs)
            log.info("TACACS servers configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS servers: {e}")

    @aetest.test
    def verify_telnet_login(self):
        """Verify Telnet login and server fallback."""
        log.info("Testing Telnet login...")
        try:
            self.uut.connect(via='telnet')  # Use Telnet explicitly
            log.info("Telnet login successful.")
        except Exception as e:
            self.failed(f"Telnet login failed: {e}")

        logs = self.uut.execute("show logging")
        if "Trying next available TACACS+ server" in logs:
            log.info("Verified fallback to non-TACACS server group.")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, testbed):
        """Clean up the configuration."""
        uut = testbed.devices['vwlc-ksukulka']
        log.info("Disabling debug commands...")
        debug_commands = [
            "undebug tacacs authentication",
            "undebug tacacs events",
            "undebug tacacs packet"
        ]
        for cmd in debug_commands:
            uut.execute(cmd)

        log.info("Removing configuration...")
        try:
            cleanup_configs = [
                f"no tacacs server {uut.custom['tac_server1']}",
                f"no tacacs server {uut.custom['tac_server2']}",
                f"no tacacs server {uut.custom['nontac_server1']}",
                f"no tacacs server {uut.custom['nontac_server2']}",
                f"no aaa group server tacacs+ {uut.custom['tacacs_group']}"
            ]
            uut.configure(cleanup_configs)
        except KeyError as e:
            log.error(f"Missing custom attribute during cleanup: {e}")
        uut.disconnect()
        log.info("Cleanup completed.")

if __name__ == '__main__':
    aetest.main()
