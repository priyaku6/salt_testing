import logging
import time
from pyats import aetest
import re

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        uut = testbed.devices['uut']
        uut.connect(via='ssh_login')
        self.parent.parameters['uut'] = uut

    @aetest.subsection
    def save_initial_config(self, uut):
        uut.api.copy_running_config_to_flash_memory(timeout=300)
        uut.api.configure_terminal_length(0)

class TacacsFailoverTest(aetest.Testcase):
    """Merged TACACS+ TLS/Non-TLS/FQDN/Failover Testcases"""

    @aetest.setup
    def setup(self, uut):
        # Get device's self-signed certificate name
        output = uut.execute('show crypto pki certificates pem | sec self')
        match = re.search(r'Trustpoint: (TP-self-signed-\d+)', output)
        if not match:
            self.failed("Could not find self-signed certificate")
        self.parent.parameters['self_cert'] = match.group(1)
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
            uut.execute(debug)

    @aetest.test
    def configure_tacacs_servers(self, uut):
        """Configure all required TACACS servers using API"""
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
            # Non-TLS server (reachable)
            {
                'host': 'NON_TLS_SERVER',
                'timeout': 10,
                'key_type': 7,
                'key': 'key2',
                'server': '192.0.2.2',
                'address_type': 'ipv4',
                'single_connection': True,
            },
            # TLS server (reachable)
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
        # TLS group (with both up and down servers)
        uut.api.configure_tacacs_group({'server_group': 'TLS_GROUP', 'server_name': 'TLS_SERVER_DOWN'})
        uut.api.configure_tacacs_group({'server_group': 'TLS_GROUP', 'server_name': 'TLS_SERVER_UP'})
        # Non-TLS group
        uut.api.configure_tacacs_group({'server_group': 'NON_TLS_GROUP', 'server_name': 'NON_TLS_SERVER'})
        # FQDN TLS group
        uut.api.configure_tacacs_group({'server_group': 'FQDN_TLS_GROUP', 'server_name': 'FQDN_TLS_SERVER'})
        # AAA config: first try TLS group, then Non-TLS group
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TLS_GROUP NON_TLS_GROUP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TLS_GROUP NON_TLS_GROUP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TLS_GROUP NON_TLS_GROUP', accounting_action='start-stop')

    @aetest.test
    def verify_failover_and_accounting(self, uut):
        """Verify failover from TLS to Non-TLS and accounting"""
        # Simulate TLS server down (ensure TLS_SERVER_DOWN is unreachable)
        # SSH login should succeed via NON_TLS_SERVER
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("SSH login successful (failover to Non-TLS)")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")
        # Privilege 15 CLI
        try:
            uut.execute('show running-config')
            log.info("Privilege 15 CLI executed successfully")
        except Exception as e:
            self.failed(f"Privilege 15 CLI failed: {str(e)}")
        # Check accounting in logs
        uut.api.clear_logging()
        uut.execute('show users')
        uut.api.verify_pattern_in_show_logging(pattern_list=['AAA/ACCT.*Accounting response status = SUCCESS', '192.0.2.2'])

    @aetest.test
    def verify_tls_success(self, uut):
        """Verify TLS server up path"""
        # Now ensure TLS_SERVER_UP is reachable and primary
        # SSH login should succeed via TLS_SERVER_UP
        uut.api.set_tacacs_server_status('TLS_SERVER_DOWN', down=True)
        uut.api.set_tacacs_server_status('TLS_SERVER_UP', down=False)
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("SSH login successful (TLS)")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")
        # Privilege 15 CLI
        uut.execute('show running-config')
        # Check logs for TLS handshake
        log_output = uut.execute("show logging")
        tls_success_patterns = [
            r"SSL Handshake successful",
            r"TLS connection established",
            r"TACACS\+\: TLS connection established",
        ]
        handshake_success = any(re.search(pattern, log_output, re.IGNORECASE) for pattern in tls_success_patterns)
        if not handshake_success:
            self.failed("Could not verify TLS handshake in logs")
        # Check accounting
        uut.api.clear_logging()
        uut.execute('show users')
        uut.api.verify_pattern_in_show_logging(pattern_list=['AAA/ACCT.*Accounting response status = SUCCESS', '192.0.2.3'])

    @aetest.test
    def fqdn_tls_server_test(self, uut):
        """Test FQDN-based TLS server"""
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='FQDN_TLS_GROUP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='FQDN_TLS_GROUP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='FQDN_TLS_GROUP', accounting_action='start-stop')
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("SSH login successful (FQDN TLS)")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")
        uut.execute('show running-config')
        log_output = uut.execute("show logging")
        if 'tacacs.example.com' not in log_output:
            self.failed("FQDN server not found in logs")
        uut.api.clear_logging()
        uut.execute('show users')
        uut.api.verify_pattern_in_show_logging(pattern_list=['AAA/ACCT.*Accounting response status = SUCCESS', 'tacacs.example.com'])

    @aetest.test
    def bulk_privilege_15_cli_and_timing(self, uut):
        """Run bulk privilege 15 commands and measure timing"""
        start = time.time()
        for _ in range(10):
            uut.execute('show running-config')
        end = time.time()
        avg_time = (end - start) / 10
        log.info(f"Average time for privilege 15 CLI: {avg_time:.2f} seconds")
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
        uut.execute('undebug all')
        uut.api.restore_running_config_file(path='flash:', file='backup_config', timeout=300)
        uut.disconnect()

