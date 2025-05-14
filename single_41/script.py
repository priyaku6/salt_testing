import logging
import re
from pyats import aetest
from pyats.log.utils import banner

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        """Connect to the device."""
        self.parent.parameters['uut'] = testbed.devices['vwlc-ksukulka']
        uut = self.parent.parameters['uut']
        uut.connect(via='ssh')

class TLSAuthorizationTest(aetest.Testcase):

    @aetest.test
    def configure_vrf_and_interface(self, uut):
        """Configure VRF and associate it with the physical interface."""
        config = f'''
            vrf definition Mgmt-vrf
            address-family ipv4
            exit-address-family
            address-family ipv6
            exit-address-family

            interface {uut.custom['source_interface']}
            vrf forwarding Mgmt-vrf
            ip address 192.168.1.2 255.255.255.0
            no shutdown
        '''
        uut.configure(config)
        log.info("VRF and interface configuration completed")

    @aetest.test
    def configure_tacacs_server(self, uut):
        """Configure TACACS+ server with TLS and VRF."""
        config = f'''
            tacacs server {uut.custom['tacacs_server_name']}
            single-connection
            address ipv4 {uut.custom['tacacs_ip']}
            tls port {uut.custom['tls_port']}
            tls idle-timeout {uut.custom['tls_idle_timeout']}
            tls connection-timeout {uut.custom['tls_connection_timeout']}
            tls retries {uut.custom['tls_retries']}
            tls ip vrf forwarding Mgmt-vrf
            tls trustpoint server ISE_TACACS_TLS_TP
            ip tacacs source-interface {uut.custom['source_interface']}
        '''
        uut.configure(config)
        log.info("TACACS+ server configuration completed")

    @aetest.test
    def configure_server_group(self, uut):
        """Configure TACACS+ server group."""
        config = f'''
            aaa group server tacacs+ {uut.custom['tacacs_server_group']}
            server name {uut.custom['tacacs_server_name']}
        '''
        uut.configure(config)
        log.info("TACACS+ server group configuration completed")

    @aetest.test
    def enable_command_accounting(self, uut):
        """Enable accounting for privilege 15 commands."""
        config = f'''
            aaa accounting commands {uut.custom['priv_level']} default start-stop group {uut.custom['tacacs_server_group']}
        '''
        uut.configure(config)
        log.info("Command accounting configuration completed")

    @aetest.test
    def execute_privilege_15_command(self, uut):
        """Execute a privilege 15 command and verify accounting."""
        try:
            output = uut.execute("show running-config")
            if output:
                log.info("Privilege 15 command executed successfully")
            else:
                self.failed("Failed to execute privilege 15 command")
        except Exception as e:
            self.failed(f"Failed to execute privilege 15 command: {str(e)}")

    @aetest.test
    def verify_accounting_logs(self, uut):
        """Verify accounting logs for privilege 15 commands."""
        try:
            logs = uut.execute("show logging | include TACACS")
            log.info("Collected TACACS+ accounting debug logs:")
            log.info(logs)

            if "Accounting method" in logs and "Accounting response status = SUCCESS" in logs:
                log.info("Accounting verification successful")
            else:
                self.failed("Accounting logs not found or verification failed")
        except Exception as e:
            self.failed(f"Failed to verify accounting logs: {str(e)}")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, uut):
        """Remove test configurations."""
        config = f'''
            no tacacs server {uut.custom['tacacs_server_name']}
            no aaa group server tacacs+ {uut.custom['tacacs_server_group']}
            no aaa accounting commands {uut.custom['priv_level']} default
            no vrf definition Mgmt-vrf

            interface {uut.custom['source_interface']}
            no vrf forwarding
            no ip address
            shutdown
        '''
        uut.configure(config)
        uut.disconnect()
        log.info("Cleanup completed")
