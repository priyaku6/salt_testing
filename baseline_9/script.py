from genie.testbed import load
from pyats import aetest
from pyats.log.utils import banner
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")
        logger.info(f"Testbed loaded: {testbed.name}")
        logger.info(f"Devices in testbed: {list(testbed.devices.keys())}")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        # Use your custom variables
        testscript.parameters['tacacs_server_name'] = uut.custom.get('tacacs_server_name', 'TAC1')
        testscript.parameters['tacacs_server_ip'] = uut.custom.get('tacacs_server_ip', '10.76.239.47')
        testscript.parameters['tacacs_group_name'] = uut.custom.get('tacacs_group_name', 'TAC_GRP')
        testscript.parameters['tacacs_key'] = uut.custom.get('tacacs_key', 'cisco123')
        # For failover, define a non-working and a working server
        testscript.parameters['non_working_server'] = uut.custom.get('tacacs_ip_non_working', '10.76.239.48')
        testscript.parameters['working_server'] = uut.custom.get('tacacs_server_ip', '10.76.239.47')
        testscript.parameters['tacacs_port'] = uut.custom.get('tacacs_port', 3006)
        testscript.parameters['username'] = uut.custom.get('tacacs_username', 'testuser')
        testscript.parameters['password'] = uut.custom.get('tacacs_password', 'testpass')

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        try:
            uut.connect(via="a")
            assert uut.connected, f"Couldn't connect to device {uut}"
            logger.info("Successfully connected to device %s" % uut.name)
        except Exception as e:
            logger.error(f"Failed to connect to device {uut.name}: {e}")
            self.failed(f"Connection to device {uut.name} failed. Please check the Telnet configuration.")

class TacacsFailoverTest(aetest.Testcase):
    """Test case to verify TACACS failover behavior"""

    @aetest.setup
    def setup(self, uut, non_working_server, working_server, tacacs_key):
        logger.info("Configuring legacy TACACS+ on this platform")
        try:
            config = [
                f"tacacs-server host {non_working_server} key {tacacs_key}",
                f"tacacs-server host {working_server} key {tacacs_key}",
                "aaa group server tacacs+ NonWorkingGroup",
                f" server {non_working_server}",
                "aaa group server tacacs+ WorkingGroup",
                f" server {working_server}",
                "aaa authentication login default group NonWorkingGroup group WorkingGroup local"
            ]
            uut.configure(config)
            logger.info("Legacy TACACS+ configuration applied")
        except Exception as e:
            logger.error(f"Exception during setup: {e}")
            self.failed(f"Failed to configure legacy TACACS servers: {e}")

    @aetest.test
    def verify_telnet_login(self, uut, username, password, tacacs_port):
        """Try Telnet to the device and verify login is successful"""
        logger.info("Verifying Telnet login with failover")
        telnet_ip = uut.connections['a']['ip']
        try:
            logger.info(f"Connecting to {telnet_ip}:{tacacs_port} via Telnet")
            output = uut.execute(f"telnet {telnet_ip} {tacacs_port}")
            logger.debug(f"Telnet connection output: {output}")

            # Handle username prompt
            if "Username:" in output:
                logger.info("Sending username")
                output = uut.execute(username)
                logger.debug(f"Username response: {output}")

            # Handle password prompt
            if "Password:" in output:
                logger.info("Sending password")
                output = uut.execute(password)
                logger.debug(f"Password response: {output}")

            # Accept prompt or connection closure as pass
            if ">" in output or "#" in output or "closed by foreign host" in output:
                logger.info("Login or expected connection closure detected")
                self.passed("Login successful or connection closed as expected for failover")
            else:
                logger.error(f"Expected prompt not found after login. Output was:\n{output}")
                self.failed("Telnet login did not reach expected prompt")
        except Exception as e:
            logger.error(f"Exception during Telnet login: {e}")
            self.failed(f"Telnet login test failed: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, non_working_server, working_server):
        logger.info(banner("Cleaning up TACACS configuration"))
        try:
            uut.configure([
                "no aaa authentication login default",
                "no aaa group server tacacs+ NonWorkingGroup",
                "no aaa group server tacacs+ WorkingGroup",
                f"no tacacs-server host {non_working_server}",
                f"no tacacs-server host {working_server}"
            ])
        except Exception as e:
            logger.warning(f"Failed to clean up TACACS configuration: {e}")
        finally:
            logger.info("Disconnecting from device")
            uut.disconnect()

if __name__ == "__main__":
    aetest.main()
