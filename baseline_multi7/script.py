import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""
    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        testscript.parameters['ise'] = testbed.devices['ise']
        testscript.parameters['non_working_tacacs'] = uut.custom['non_working_tacacs']
        testscript.parameters['working_tacacs'] = uut.custom['working_tacacs']
        testscript.parameters['tacacs_key'] = uut.custom['tacacs_key']

    @aetest.subsection
    def connect_devices(self, uut, ise):
        logger.info(banner("Connecting to devices..."))
        uut.connect()
        ise.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        assert ise.connected, f"Couldn't connect to ISE {ise}"

class ConfigureISEandTACACS(aetest.Testcase):
    """Configure ISE and TACACS server groups"""

    @aetest.setup
    def setup(self, ise):
        logger.info("Configuring ISE to enable TACACS")
        # Replace with actual API/CLI to enable TACACS on ISE
        ise.api.enable_tacacs()

    @aetest.test
    def configure_tacacs_groups(self, uut, non_working_tacacs, working_tacacs, tacacs_key):
        logger.info("Configuring TACACS server groups")
        # Configure non-working TACACS server group
        uut.api.configure_tacacs_server_group(
            group_name="NONWORKING",
            servers=[non_working_tacacs],
            key=tacacs_key
        )
        # Configure working TACACS server group
        uut.api.configure_tacacs_server_group(
            group_name="WORKING",
            servers=[working_tacacs],
            key=tacacs_key
        )

    @aetest.test
    def configure_login_authentication(self, uut):
        logger.info("Enabling login authentication with TACACS groups")
        # Set authentication order: non-working group first, then working group
        uut.api.configure_login_authentication(
            method_list="default",
            groups=["NONWORKING", "WORKING"]
        )

class SSHLoginTest(aetest.Testcase):
    """Test SSH login using TACACS group authentication"""

    @aetest.test
    def ssh_login(self, uut):
        logger.info("Attempting SSH login to device")
        # Replace with actual SSH login logic, e.g., using paramiko or device API
        result = uut.api.ssh_login(uut.connections['ssh']['ip'])
        if result['success']:
            logger.info("SSH login successful")
        else:
            self.failed("SSH login failed")

    @aetest.test
    def verify_login(self, uut):
        logger.info("Verifying login is successful")
        # Replace with actual verification logic
        assert uut.api.is_logged_in(), "Login verification failed"

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut):
        logger.info(banner("Cleaning up TACACS configuration"))
        uut.api.remove_tacacs_server_group("NONWORKING")
        uut.api.remove_tacacs_server_group("WORKING")
        uut.api.remove_login_authentication("default")

    @aetest.subsection
    def disconnect_devices(self, uut, ise):
        logger.info(banner("Disconnecting from devices"))
        uut.disconnect()
        ise.disconnect()
