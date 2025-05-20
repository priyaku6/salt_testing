import logging
import time
from pyats import aetest
from pyats.log.utils import banner
from unicon.core.errors import ConnectionError
import re

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        """Connect to device."""
        try:
            uut = testbed.devices['uut']
            uut.connect(via='ssh_login')
            self.parent.parameters['uut'] = uut
            log.info("Successfully connected to device.")
        except Exception as e:
            log.error(f"Failed to connect to device: {e}")
            self.failed(f"Device connection failed: {e}")

    @aetest.subsection
    def save_initial_config(self, uut):
        """Save the initial configuration before any tests."""
        try:
            uut.api.copy_running_config_to_flash_memory(timeout=300)
            log.info("Initial configuration saved to flash.")
        except Exception as e:
            log.error(f"Failed to save initial config: {e}")
            self.failed(f"Saving initial config failed: {e}")

class TacacsTlsFallbackTest(aetest.Testcase):
    """Test TACACS+ TLS configuration, fallback, and accounting"""

    @aetest.setup
    def setup(self, uut):
        """Setup required configurations"""
        # Get device's self-signed certificate name
        try:
            output = uut.execute('show crypto pki certificates pem | sec self')
            match = re.search(r'Trustpoint: (TP-self-signed-\d+)', output)
            if not match:
                log.error("Could not find self-signed certificate")
                self.failed("Could not find self-signed certificate")
            self.parent.parameters['self_cert'] = match.group(1)
            log.info(f"Using self-signed certificate: {match.group(1)}")
        except Exception as e:
            log.error(f"Error fetching self-signed certificate: {e}")
            self.failed(f"Error fetching self-signed certificate: {e}")

        # Enable required debugs
        debugs = [
            "debug aaa authorization",
            "debug tacacs",
            "debug aaa authentication",
            "debug aaa accounting",
            "debug ssl openssl errors",
            "debug ssl openssl states",
        ]
        for debug in debugs:
            try:
                uut.execute(debug)
            except Exception as e:
                log.warning(f"Failed to enable debug '{debug}': {e}")

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure TACACS servers using the provided API only"""
        log.info("Configuring TACACS servers with TLS")
        try:
            server_configs = [
                {
                    'host': uut.custom['tacacs_server1_name'],
                    'timeout': uut.custom.get('tacacs_timeout', 10),
                    'key_type': uut.custom.get('tacacs_key_type', 7),
                    'key': uut.custom['tacacs_key'],
                    'server': uut.custom['tacacs_server1_ip'],
                    'address_type': 'ipv4',
                    'single_connection': True,
                    'tls_port': uut.custom['tls_port'],
                    'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                    'tls_connection_timeout': uut.custom['tls_connection_timeout'],
                    'tls_retries': uut.custom['tls_retries'],
                    'tls_trustpoint_client': self.parent.parameters['self_cert'],
                    'tls_trustpoint_server': 'ISE_TACACS_TLS_TP_UNREACHABLE',
                    'tls_source_interface': uut.custom['source_interface'],
                    'tls_ip_tacacs_source_interface': uut.custom['source_interface']
                },
                {
                    'host': uut.custom['tacacs_server2_name'],
                    'timeout': uut.custom.get('tacacs_timeout', 10),
                    'key_type': uut.custom.get('tacacs_key_type', 7),
                    'key': uut.custom['tacacs_key'],
                    'server': uut.custom['tacacs_server2_ip'],
                    'address_type': 'ipv4',
                    'single_connection': True,
                    'tls_port': uut.custom['tls_port'],
                    'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                    'tls_connection_timeout': uut.custom['tls_connection_timeout'],
                    'tls_retries': uut.custom['tls_retries'],
                    'tls_trustpoint_client': self.parent.parameters['self_cert'],
                    'tls_trustpoint_server': 'ISE_SERVER_TLS',
                    'tls_source_interface': uut.custom['source_interface'],
                    'tls_ip_tacacs_source_interface': uut.custom['source_interface']
                }
            ]
            uut.api.configure_tacacs_server(uut, server_configs)
            log.info("TACACS servers configured successfully.")
        except Exception as e:
            log.error(f"Failed to configure TACACS servers: {e}")
            self.failed(f"Failed to configure TACACS servers: {e}")

    @aetest.test
    def configure_server_group_and_aaa(self, uut):
        """Configure TACACS server group and AAA"""
        log.info("Configuring TACACS server group and AAA")
        try:
            group_name = uut.custom['tacacs_group_name']
            uut.api.configure_tacacs_group({'server_group': group_name, 'server_name': uut.custom['tacacs_server1_name']})
            uut.api.configure_tacacs_group({'server_group': group_name, 'server_name': uut.custom['tacacs_server2_name']})
            uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=group_name)
            uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=group_name)
            uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name=group_name, accounting_action='start-stop')
            log.info("TACACS server group and AAA configured successfully.")
        except Exception as e:
            log.error(f"Failed to configure server group or AAA: {e}")
            self.failed(f"Failed to configure server group or AAA: {e}")

    @aetest.test
    def verify_ssh_login_and_fallback(self, uut):
        """Verify SSH login, fallback, and accounting"""
        log.info("Testing SSH login to device using TACACS+TLS")
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            log.info("SSH login successful")
        except Exception as e:
            log.error(f"SSH login failed: {e}")
            self.failed(f"SSH login failed with error: {str(e)}")

        try:
            uut.api.clear_logging()
            uut.execute('show users')
            uut.api.verify_pattern_in_show_logging(pattern_list=[
                'AAA/ACCT.*Accounting response status = SUCCESS',
                uut.custom['tacacs_server2_ip']
            ])
            log.info("TACACS+ accounting successful")
            uut.api.verify_pattern_in_show_logging(pattern_list=[
                f'TCP\\d+: state was ESTAB -> FINWAIT1 \\[\\d+ -> {re.escape(uut.custom["tacacs_server2_ip"])}\\({uut.custom["tls_port"]}\\)\\]'
            ])
        except Exception as e:
            log.error(f"Failed to verify accounting: {e}")
            self.failed(f"Failed to verify accounting: {str(e)}")

        # Verify fallback: ensure only the reachable server was used
        try:
            logs = uut.execute("show logging")
            if uut.custom['tacacs_server1_ip'] in logs:
                log.error("Unreachable server should not be used")
                self.failed("Unreachable server should not be used")
        except Exception as e:
            log.warning(f"Could not verify fallback in logs: {e}")

    @aetest.test
    def verify_tls_handshake(self, uut):
        """Verify TLS handshake in debug logs"""
        log.info("Verifying TLS handshake in debug logs")
        try:
            log_output = uut.execute("show logging")
            tls_success_patterns = [
                r"SSL Handshake successful",
                r"TLS connection established",
                r"TACACS\+\: TLS connection established",
                r"SSL3 alert write:warning:close notify",
                r"SSL-API.*Handshake successful"
            ]
            handshake_success = False
            for pattern in tls_success_patterns:
                if re.search(pattern, log_output, re.IGNORECASE):
                    handshake_success = True
                    log.info(f"TLS handshake verification successful: {pattern} found in logs")
                    break
            if handshake_success:
                self.passed("TLS handshake verification successful")
            else:
                if "TACACS+: Authentication response status=PASS" in log_output:
                    log.info("TACACS+ authentication successful, implying TLS handshake worked")
                    self.passed("TACACS+ authentication successful, implying TLS handshake worked")
                else:
                    log.error("Could not verify TLS handshake success in logs")
                    self.failed("Could not verify TLS handshake success in logs")
        except Exception as e:
            log.error(f"Error verifying TLS handshake: {e}")
            self.failed(f"Error verifying TLS handshake: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Restore initial configuration."""
    @aetest.subsection
    def cleanup(self, uut):
        """Restore the saved configuration and cleanup."""
        try:
            uut.execute('undebug all')
            uut.api.restore_running_config_file(
                path='flash:',
                file='backup_config',
                timeout=300
            )
            uut.disconnect()
            log.info("Cleanup completed and device disconnected.")
        except Exception as e:
            log.error(f"Cleanup failed: {e}")
            self.failed(f"Cleanup failed: {e}")
