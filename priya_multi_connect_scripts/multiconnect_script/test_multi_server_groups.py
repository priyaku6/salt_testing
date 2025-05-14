import logging
from pyats import aetest
from pyats.log.utils import banner
from pyats.topology import loader

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_device(self, testbed_file='testbed.yaml'):
        """Connect to the device"""
        log.info(banner("Connecting to the device"))
        try:
            # Load the testbed
            testbed = loader.load(testbed_file)

            # Ensure the 'uut' alias exists in the testbed
            if 'uut' not in testbed.devices:
                self.failed("Device alias 'uut' not found in the testbed.")

            # Connect to the device
            self.device = testbed.devices['uut']
            self.device.connect()

            # Store test parameters
            self.parent.parameters.update({
                'uut': self.device,
                'initial_config': self.device.execute('show running-config')
            })
        except Exception as e:
            self.failed(f"Failed to connect to the device: {e}")


class MultiServerTest(aetest.Testcase):
    """Test case for multi-server TACACS configuration"""

    @aetest.setup
    def setup(self, uut):
        """Configure initial setup"""
        log.info(banner("Enabling debug commands"))
        try:
            uut.execute("terminal monitor")
            debug_commands = [
                "debug tacacs authentication",
                "debug tacacs authorization"
            ]
            for cmd in debug_commands:
                uut.execute(cmd)
        except Exception as e:
            self.failed(f"Failed to enable debug commands: {e}")

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure TACACS servers"""
        log.info(banner("Configuring TACACS servers"))
        try:
            # Use device-specific commands for TACACS configuration
            configs = [
                "tacacs server NonTLS_Server1",
                " address ipv4 192.168.1.1",
                " key cisco",
                "exit",
                "tacacs server NonTLS_Server2",
                " address ipv4 192.168.1.2",
                " key cisco",
                "exit",
                "aaa group server tacacs+ NonTLS_Group",
                " server name NonTLS_Server1",
                " server name NonTLS_Server2",
                "exit"
            ]
            uut.configure("\n".join(configs))  # Ensure commands are executed in config mode
        except Exception as e:
            self.failed(f"Failed to configure TACACS servers: {e}")

    @aetest.test
    def configure_aaa(self, uut):
        """Configure AAA authentication and authorization"""
        log.info(banner("Configuring AAA"))
        try:
            configs = [
                "aaa new-model",
                "aaa authentication login default group NonTLS_Group",
                "aaa authorization commands 15 default group NonTLS_Group"
            ]
            uut.configure("\n".join(configs))  # Ensure commands are executed in config mode
        except Exception as e:
            self.failed(f"Failed to configure AAA: {e}")

    @aetest.test
    def add_boot_image(self, uut):
        """Add a new boot image to the configuration"""
        log.info(banner("Adding new boot image to the configuration"))
        try:
            uut.configure("""
                boot system bootflash:/auto/tftp-blr-users1/malallur/saltfoon/C9800-CL-universalk9.2025-03-24_17.34_malallur.SSA.bin
            """)
            log.info("New boot image added successfully")
        except Exception as e:
            self.failed(f"Failed to add new boot image: {e}")

    @aetest.test
    def verify_boot_image(self, uut):
        """Verify the new boot image configuration"""
        log.info(banner("Verifying new boot image configuration"))
        try:
            output = uut.execute("show running-config | include boot system")
            if "/auto/tftp-blr-users1/malallur/saltfoon/C9800-CL-universalk9.2025-03-24_17.34_malallur.SSA.bin" in output:
                log.info("New boot image verified successfully")
            else:
                self.failed("New boot image not found in the configuration")
        except Exception as e:
            self.failed(f"Failed to verify new boot image: {e}")

    @aetest.test
    def verify_authentication(self, uut):
        """Verify SSH authentication"""
        log.info(banner("Verifying SSH authentication"))
        try:
            output = uut.execute("show running-config | include aaa authentication")
            if "group NonTLS_Group" not in output:
                self.failed("AAA authentication configuration is incorrect")
        except Exception as e:
            self.failed(f"Failed to verify authentication: {e}")

    @aetest.test
    def verify_authorization(self, uut):
        """Verify command authorization"""
        log.info(banner("Verifying command authorization"))
        try:
            output = uut.execute("show running-config | include aaa authorization")
            if "group NonTLS_Group" not in output:
                self.failed("AAA authorization configuration is incorrect")
        except Exception as e:
            self.failed(f"Failed to verify authorization: {e}")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup section"""

    @aetest.subsection
    def cleanup(self, uut, initial_config):
        """Restore initial configuration"""
        log.info(banner("Restoring initial configuration"))
        if not uut or not initial_config:
            self.failed("Missing required parameters 'uut' or 'initial_config'.")

        try:
            # Disable debugs
            debug_commands = [
                "no debug tacacs authentication",
                "no debug tacacs authorization"
            ]
            for cmd in debug_commands:
                uut.execute(cmd)

            # Filter valid configuration lines
            valid_config_lines = [
                line.strip() for line in initial_config.splitlines()
                if line.strip() and not line.startswith((
                    "Building configuration",
                    "Current configuration",
                    "quit",
                    "Enter the certificate",
                    "% This is an internal command"
                ))
            ]

            # Restore initial configuration in config mode
            uut.configure("\n".join(valid_config_lines))
            uut.execute("write memory")  # Save the configuration
        except Exception as e:
            self.failed(f"Failed during cleanup: {e}")


if __name__ == '__main__':
    aetest.main()
