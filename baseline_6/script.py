from pyats import aetest  # type: ignore
from pyats.log.utils import banner  # type: ignore
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_testbed(self, testbed):
        """Validate the testbed information"""
        logger.info(banner("Validating Testbed"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed):
        """Initialize test variables"""
        logger.info(banner("Initializing Variables"))
        uut = testbed.devices['uut']
        try:
            self.parent.parameters.update({
                'uut': uut,
                'tacacs_servers': uut.custom['tacacs_servers'],
                'tacacs_group': uut.custom['tacacs_group'],
                'telnet_ip': uut.connections['a']['ip'],
                'telnet_port': uut.connections['a']['port']
            })
        except KeyError as e:
            logger.error(f"Missing required custom variable in testbed: {e}")
            self.failed(f"Missing required custom variable: {e}")

    @aetest.subsection
    def connect_device(self, uut):
        """Connect to the device"""
        logger.info(banner("Connecting to the Device"))
        try:
            uut.connect()
        except Exception as e:
            logger.error(f"Initial connection failed: {e}")
            self.failed("Failed to connect to the device.")

        assert uut.connected, f"Failed to connect to device {uut.name}"


class ConfigureTacacs(aetest.Testcase):
    """Test case to configure TACACS servers and authentication"""

    @aetest.setup
    def setup(self, uut, tacacs_servers, tacacs_group):
        """Configure TACACS servers and group"""
        logger.info("Configuring TACACS servers")
        for server in tacacs_servers:
            try:
                # Verify if the TACACS server is already configured
                output = uut.execute(f"show running-config | include tacacs server {server['server']}")
                if f"tacacs server {server['server']}" in output:
                    logger.info(f"TACACS server {server['server']} is already configured")
                    continue

                # Configure TACACS server
                commands = [
                    f"tacacs server {server['server']}",
                    f" address ipv4 {server['server']}",
                    f" key {server['key']}",
                    " single-connection"
                ]
                logger.info(f"Configuring TACACS server with commands: {commands}")
                uut.configure(commands)
            except Exception as e:
                logger.error(f"Failed to configure TACACS server {server['server']}: {e}")
                self.failed(f"Failed to configure TACACS server {server['server']} due to invalid input.")

        try:
            # Configure TACACS group
            group_commands = [
                f"aaa group server tacacs+ {tacacs_group}",
                f" server name {tacacs_servers[0]['server']}",
                f" server name {tacacs_servers[1]['server']}",
                f"aaa authentication login default group {tacacs_group}"
            ]
            logger.info(f"Configuring TACACS group with commands: {group_commands}")
            uut.configure(group_commands)
        except Exception as e:
            logger.error(f"Failed to configure TACACS group {tacacs_group}: {e}")
            self.failed(f"Failed to configure TACACS group {tacacs_group}.")

    @aetest.test
    def verify_telnet_login(self, uut, telnet_ip, telnet_port):
        """Verify Telnet login using TACACS"""
        logger.info("Verifying Telnet login")
        uut.disconnect()
        try:
            uut.connect(via='a')  # Use the Telnet connection
            assert uut.connected, "Telnet login failed"
            logger.info("Telnet login successful")
        except Exception as e:
            logger.error(f"Telnet login failed: {e}")
            self.failed("Telnet login failed")


class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_servers, tacacs_group):
        """Remove TACACS configuration"""
        logger.info(banner("Cleaning up TACACS Configuration"))
        try:
            # Ensure the device is connected before attempting cleanup
            if not uut.connected:
                logger.warning("Device is not connected. Attempting to reconnect...")
                uut.connect()

            # Remove TACACS server configurations
            for server in tacacs_servers:
                try:
                    uut.configure([f"no tacacs server {server['server']}"])
                except Exception as e:
                    logger.warning(f"Failed to remove TACACS server {server['server']}: {e}")

            # Remove TACACS group configuration
            try:
                uut.configure([
                    f"no aaa group server tacacs+ {tacacs_group}",
                    "no aaa authentication login default"
                ])
            except Exception as e:
                logger.warning(f"Failed to remove TACACS group {tacacs_group}: {e}")

            logger.info("TACACS configuration cleaned up successfully.")
        except Exception as e:
            logger.error(f"Failed to clean up TACACS configuration: {e}")
            self.errored(f"Cleanup failed due to: {e}")

    @aetest.subsection
    def disconnect_device(self, uut):
        """Disconnect from the device"""
        logger.info(banner("Disconnecting from Device"))
        try:
            if uut.connected:
                uut.disconnect()
                logger.info("Device disconnected successfully.")
            else:
                logger.warning("Device was already disconnected.")
        except Exception as e:
            logger.error(f"Failed to disconnect from the device: {e}")
            self.errored(f"Disconnection failed due to: {e}")
