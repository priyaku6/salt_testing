import logging
import time
from pyats import aetest
from pyats.log.utils import banner
import re

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        """Connect to device."""
        uut = testbed.devices['uut']
        uut.connect(via='ssh_login')
        self.parent.parameters['uut'] = uut

    @aetest.subsection
    def save_initial_config(self, uut):
        """Save the initial configuration before any tests."""
        uut.api.copy_running_config_to_flash_memory(timeout=300)
        uut.api.configure_terminal_length(0)

class TacacsMergedTest(aetest.Testcase):
    """Merged TACACS+ TLS/Non-TLS Testcases"""

    @aetest.setup
    def setup(self, uut):
        """Enable required debugs and get trustpoint"""
        output = uut.execute('show crypto pki certificates pem | sec self')
        match = re.search(r'Trustpoint: (TP-self-signed-\d+)', output)
        if not match:
            self.failed("Could not find self-signed certificate")
        self.parent.parameters['self_cert'] = match.group(1)
        debugs = [
            "debug aaa authorization",
            "debug tacacs",
            "debug aaa authentication",
            "debug aaa accounting",
            "debug aaa subsys",
            "debug aaa protocol local",
            "debug tacacs events",
            "debug tacacs packet",
            "debug tacacs accounting",
            "debug tacacs authorization",
            "debug tacacs authentication",
            "debug ssl openssl errors",
            "debug ssl openssl states",
        ]
        for debug in debugs:
            uut.execute(debug)

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure all required TACACS servers using API"""
        # Example server configs, fill in with your actual values
        server_configs = [
            # TLS server (simulate not working)
            {
                'host': 'TLS_SERVER_DOWN',
                'timeout': 10,
                'key_type': 7,
                'key': 'key1',
                'server': '192.0.2.1',
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': 49,
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': 'TP_TLS_DOWN',
                'tls_source_interface': 'GigabitEthernet0/0',
            },
            # Non-TLS server
            {
                'host': 'NON_TLS_SERVER',
                'timeout': 10,
                'key_type': 7,
                'key': 'key2',
                'server': '192.0.2.2',
                'address_type': 'ipv4',
                'single_connection': True,
            },
            # TLS server (working)
            {
                'host': 'TLS_SERVER_UP',
                'timeout': 10,
                'key_type': 7,
                'key': 'key3',
                'server': '192.0.2.3',
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': 49,
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': 'TP_TLS_UP',
                'tls_source_interface': 'GigabitEthernet0/0',
            },
            # FQDN server with TLS
            {
                'host': 'FQDN_TLS_SERVER',
                'timeout': 10,
                'key_type': 7,
                'key': 'key4',
                'server': 'tacacs.example.com',
                'address_type': 'hostname',
                'single_connection': True,
                'tls_port': 49,
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': 'TP_FQDN_TLS',
                'tls_source_interface': 'GigabitEthernet0/0',
            }
        ]
        uut.api.configure_tacacs_server(server_configs)

    @aetest.test
    def configure_server_groups_and_aaa(self, uut):
        """Configure server groups and AAA using available APIs"""
        # Example: configure two groups, one for TLS, one for Non-TLS
        uut.api.configure_tacacs_group({'server_group': 'TLS_GROUP', 'server_name': 'TLS_SERVER_UP'})
        uut.api.configure_tacacs_group({'server_group': 'NON_TLS_GROUP', 'server_name': 'NON_TLS_SERVER'})
        uut.api.configure_tacacs_group({'server_group': 'FQDN_TLS_GROUP', 'server_name': 'FQDN_TLS_SERVER'})
        # Configure AAA for login, authorization, and accounting
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TLS_GROUP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TLS_GROUP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TLS_GROUP', accounting_action='start-stop')

    @aetest.test
    def verify_ssh_login_and_privilege(self, uut):
        """Verify SSH login, privilege 15 CLI, authorization, and accounting"""
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("SSH login successful")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")
        # Try privilege 15 CLI
        try:
            uut.execute('show running-config')
            log.info("Privilege 15 CLI executed successfully")
        except Exception as e:
            self.failed(f"Privilege 15 CLI failed: {str(e)}")
        # Check accounting in logs
        uut.api.clear_logging()
        uut.execute('show users')
        uut.api.verify_pattern_in_show_logging(pattern_list=['AAA/ACCT.*Accounting response status = SUCCESS'])

    @aetest.test
    def verify_tls_handshake_in_logs(self, uut):
        """Verify TLS handshake in debug logs"""
        log_output = uut.execute("show logging")
        tls_success_patterns = [
            r"SSL Handshake successful",
            r"TLS connection established",
            r"TACACS\+\: TLS connection established",
        ]
        handshake_success = any(re.search(pattern, log_output, re.IGNORECASE) for pattern in tls_success_patterns)
        if handshake_success:
            self.passed("TLS handshake verification successful")
        else:
            self.failed("Could not verify TLS handshake in logs")

    @aetest.test
    def bulk_privilege_15_cli_and_timing(self, uut):
        """Run bulk privilege 15 commands and measure timing"""
        start = time.time()
        for _ in range(10):
            uut.execute('show running-config')
        end = time.time()
        avg_time = (end - start) / 10
        log.info(f"Average time for privilege 15 CLI: {avg_time:.2f} seconds")
        # Check for crashes/tracebacks
        logs = uut.execute('show logging')
        if "crash" in logs.lower() or "traceback" in logs.lower():
            self.failed("Crash or traceback found in logs")
        else:
            self.passed("No crash or traceback found")

    @aetest.test
    def remove_add_server_group_loop(self, uut):
        """Remove and add TACACS server/group configs in a loop"""
        for _ in range(3):
            uut.api.remove_tacacs_group('TLS_GROUP')
            uut.api.configure_tacacs_group({'server_group': 'TLS_GROUP', 'server_name': 'TLS_SERVER_UP'})
        self.passed("Remove/add server group loop completed")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, uut):
        """Restore the saved configuration and cleanup."""
        uut.execute('undebug all')
        uut.api.restore_running_config_file(path='flash:', file='backup_config', timeout=300)
        uut.disconnect()

