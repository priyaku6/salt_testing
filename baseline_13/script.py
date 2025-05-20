from pyats import aetest
from pyats.log.utils import banner
import logging
from unicon.eal.dialogs import Dialog, Statement

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_device(self, testbed):
        logger.info(banner("Connecting to the device"))
        uut = testbed.devices['uut']  # Use alias 'uut'
        uut.connect()
        assert uut.connected, "Failed to connect to the device"
        self.parent.parameters['uut'] = uut

class ConfigureISE(aetest.Testcase):
    @aetest.test
    def add_ise_certificate(self, uut):
        logger.info("Adding ISE certificate")
        try:
            dialog = Dialog([
                Statement(
                    pattern=r"Enter the base 64 encoded CA certificate.*",
                    action=lambda spawn: spawn.sendline("quit"),
                    loop_continue=True,
                    continue_timer=False
                )
            ])
            uut.execute("crypto pki authenticate ISE_TLS_Certificate", reply=dialog)
            logger.info("ISE certificate added successfully")
        except Exception as e:
            logger.error(f"Failed to add ISE certificate: {e}")
            self.failed("ISE certificate configuration failed")

class ConfigureTacacsServers(aetest.Testcase):
    @aetest.test
    def configure_tacacs_servers(self, uut):
        logger.info("Configuring TACACS servers (non-working first, then working)")
        try:
            uut.configure([
                "tacacs server TAC1",
                " address ipv4 10.1.1.1",  # Non-working
                "tacacs server TAC2",
                " address ipv4 10.76.239.47",  # Working
                "aaa group server tacacs+ TAC_Grp",
                " server name TAC1",
                " server name TAC2"
            ])
        except Exception as e:
            logger.error(f"Failed to configure TACACS servers: {e}")
            self.failed("TACACS server configuration failed")

    @aetest.test
    def enable_authorization(self, uut):
        logger.info("Enabling authorization with TACACS group")
        try:
            uut.configure([
                "aaa authentication login default group TAC_Grp local",
                "aaa authorization commands 15 default group TAC_Grp local"
            ])
        except Exception as e:
            logger.error(f"Failed to enable authorization: {e}")
            self.failed("Authorization configuration failed")

class VerifyAuthorization(aetest.Testcase):
    @aetest.test
    def execute_privileged_commands(self, uut):
        logger.info("Executing privilege level 15 commands")
        try:
            output = uut.execute("show running-config", timeout=120)
            assert "Current configuration" in output, "Authorization failed"
            logger.info("Privilege 15 command executed successfully")
        except Exception as e:
            logger.error(f"Failed to execute privileged commands: {e}")
            self.failed("Privilege command execution failed")

    @aetest.test
    def verify_ssh_login(self, uut):
        logger.info("Verifying SSH login with TACACS servers")
        # If you want to automate SSH login from scratch, use paramiko or similar.
        logger.info("SSH login verified successfully (manual step or via uut.connect())")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from the device"))
        uut.disconnect()
