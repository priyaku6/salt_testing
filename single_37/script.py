import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the test device"""
        self.device = testbed.devices['vwlc-ksukulka']
        self.device.connect(via='ssh')  # Connect using SSH
        self.parent.parameters['device'] = self.device  # Pass the device to test cases

class TacacsConfigurationTest(aetest.Testcase):
    """Test TACACS+ server configuration"""

    @aetest.setup
    def setup(self, device):
        """Enable required debugs"""
        debug_commands = [
            "terminal monitor",
            "debug aaa authentication",
            "debug aaa authorization",
            "debug aaa accounting",
            "debug tacacs events",
            "debug tacacs accounting"
        ]
        for cmd in debug_commands:
            try:
                device.execute(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute debug command '{cmd}': {str(e)}")
        logger.info("Debugs enabled successfully.")

    @aetest.test
    def configure_tacacs_server(self, device):
        """Configure TACACS+ server and enable TLS"""
        try:
            tacacs_config = [
                "tacacs server TAC",
                " address ipv4 10.76.239.47",
                " key cisco123",
                " port 6049",
                " timeout 32",
                " tls"
            ]
            device.configure(tacacs_config)

            server_group_config = [
                "aaa group server tacacs+ TAC_Grp",
                " server name TAC",
                " ip tacacs source-interface GigabitEthernet1"
            ]
            device.configure(server_group_config)

            logger.info("TACACS+ server and server group configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure TACACS+ server: {str(e)}")

    @aetest.test
    def configure_login_authentication(self, device):
        """Configure login authentication using TACACS+ server group"""
        try:
            login_auth_config = [
                "aaa authentication login default group TAC_Grp local",
                "aaa authorization exec default group TAC_Grp local"
            ]
            device.configure(login_auth_config)
            logger.info("Login authentication configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure login authentication: {str(e)}")

    @aetest.test
    def configure_ip_host(self, device):
        """Configure IP host to resolve tacacs.com to ISE IP"""
        try:
            ip_host_config = [
                "ip host tacacs.com 10.76.239.47"
            ]
            device.configure(ip_host_config)
            logger.info("IP host configured successfully.")
        except Exception as e:
            self.failed(f"Failed to configure IP host: {str(e)}")

    @aetest.test
    def verify_ssh_login(self, device):
        """Perform SSH login and verify success"""
        try:
            # Verify hostname resolution
            output = device.execute("ping tacacs.com")
            if "!!!!" not in output:
                self.failed("Hostname 'tacacs.com' could not be resolved to the correct IP.")

            # Try SSH login with different formats
            ssh_commands = [
                "ssh ksukulka@tacacs.com@10.76.239.180",
                "ssh ksukulka@tacacs.com",
                "ssh -l ksukulka tacacs.com",
                "ssh ksukulka@10.76.239.180"
            ]

            for ssh_command in ssh_commands:
                try:
                    logger.info(f"Attempting SSH login with command: {ssh_command}")
                    output = device.execute(ssh_command)
                    if "Password:" in output:
                        logger.info(f"SSH login prompt received successfully using command: {ssh_command}")
                        return
                except Exception as e:
                    logger.warning(f"SSH command failed: {ssh_command} - {str(e)}")

            # Log additional debugging information
            logger.error("SSH login failed with all attempted formats.")
            logger.info("Collecting additional debugging information...")
            debug_output = device.execute("show running-config | include tacacs")
            logger.info(f"TACACS+ Configuration: {debug_output}")
            debug_output = device.execute("show ip ssh")
            logger.info(f"SSH Configuration: {debug_output}")

            self.failed("SSH login failed with all attempted formats.")
        except Exception as e:
            self.failed(f"Failed to perform SSH login: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup(self, device):
        """Remove test configuration"""
        cleanup_cmds = [
            "no tacacs server TAC",
            "no aaa group server tacacs+ TAC_Grp",
            "no aaa authentication login default",
            "no aaa authorization exec default",
            "no ip host tacacs.com",
            "no debug all"
        ]
        try:
            device.configure(cleanup_cmds)
            logger.info("Cleanup completed successfully.")
        except Exception as e:
            logger.warning(f"Failed to clean up configuration: {str(e)}")
