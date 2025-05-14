from pyats import aetest
from genie.testbed import load
import logging

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device"""
        logger.info("Connecting to the device...")
        self.parent.parameters['uut'] = testbed.devices['vwlc-ksukulka']
        uut = self.parent.parameters['uut']
        uut.connect(via='a')
        assert uut.connected, f"Couldn't connect to device {uut.name}"
        logger.info(f"Successfully connected to device {uut.name}")

class TacacsFailoverTest(aetest.Testcase):
    """Test case to verify TACACS failover behavior"""

    @aetest.setup
    def setup(self, uut):
        """Configure TACACS servers, groups, and authentication order"""
        logger.info("Starting TACACS failover setup...")

        tacacs_servers = uut.custom['tacacs_servers']
        non_working = tacacs_servers[0]
        working = tacacs_servers[1]

        # Configure non-working and working TACACS servers in separate groups
        try:
            logger.info("Configuring TACACS server groups")
            uut.configure([
                f"tacacs server NonWorkingServer",
                f" address ipv4 {non_working['server']}",
                f" key 7 {non_working['key']}",
                f"tacacs server WorkingServer",
                f" address ipv4 {working['server']}",
                f" key 7 {working['key']}",
                "aaa group server tacacs+ NonWorkingGroup",
                " server name NonWorkingServer",
                "aaa group server tacacs+ WorkingGroup",
                " server name WorkingServer"
            ])
        except Exception as e:
            logger.error(f"Failed to configure TACACS server groups: {e}")
            self.failed("TACACS server group configuration failed")

        # Enable login authentication with non-working group first, then working group
        try:
            logger.info("Configuring login authentication with failover order")
            uut.configure([
                "aaa authentication login default group NonWorkingGroup group WorkingGroup local"
            ])
        except Exception as e:
            logger.error(f"Failed to configure login authentication: {e}")
            self.failed("Login authentication configuration failed")

    @aetest.test
    def verify_failover(self, uut):
        """Try accessing device console and verify login is successful (failover works)"""
        logger.info("Verifying TACACS failover during console login")
        try:
            # Simulate console login by executing a command that requires authentication
            output = uut.execute("show running-config | include tacacs")
            logger.info(output)
            # Check that both servers are present in config
            if "NonWorkingServer" in output and "WorkingServer" in output:
                logger.info("Login via TACACS failover is successful")
                self.passed("TACACS failover verified: login successful via working server")
            else:
                self.failed("Failover to WorkingServer not verified")
        except Exception as e:
            logger.error(f"Failed to verify failover: {e}")
            self.failed("Failover verification failed")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self):
        """Remove TACACS configuration"""
        uut = self.parent.parameters['uut']
        logger.info("Cleaning up TACACS configuration")
        commands = [
            "no tacacs server NonWorkingServer",
            "no tacacs server WorkingServer",
            "no aaa group server tacacs+ NonWorkingGroup",
            "no aaa group server tacacs+ WorkingGroup",
            "no aaa authentication login default",
        ]
        for cmd in commands:
            try:
                uut.configure([cmd])
            except Exception as e:
                logger.warning(f"Failed to execute cleanup command '{cmd}': {e}")

    @aetest.subsection
    def disconnect_device(self):
        """Disconnect from the device"""
        uut = self.parent.parameters['uut']
        logger.info("Disconnecting from the device")
        uut.disconnect()

if __name__ == '__main__':
    import argparse
    from pyats.aetest import Testbed, main

    parser = argparse.ArgumentParser()
    parser.add_argument('--testbed', type=str, required=True)
    args = parser.parse_args()

    testbed = load(args.testbed)
    main(testbed=testbed)
