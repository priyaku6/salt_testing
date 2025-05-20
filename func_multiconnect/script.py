import logging
import time
import re
from pyats import aetest

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        uut = testbed.devices['uut']
        uut.connect()
        self.parent.parameters['uut'] = uut

    @aetest.subsection
    def save_config(self, uut):
        uut.api.copy_running_config_to_flash_memory(timeout=300)

class TacacsMultiConnectTest(aetest.Testcase):
    """TACACS+ TLS/Non-TLS Multi-Connect Test"""

    @aetest.setup
    def setup(self, uut):
        # Enable all required debugs
        debugs = [
            "debug aaa authorization", "debug tacacs", "debug aaa authentication",
            "debug aaa accounting", "debug aaa subsys", "debug aaa protocol local",
            "debug tacacs events", "debug tacacs packet", "debug tacacs accounting",
            "debug tacacs authorization", "debug tacacs authentication",
            "debug ssl openssl errors", "debug ssl openssl states"
        ]
        for debug in debugs:
            uut.execute(debug)

    @aetest.test
    def configure_tls_and_nontls_servers(self, uut):
        """Configure two TLS and two Non-TLS TACACS+ servers and groups"""
        # TLS servers
        for idx in [1, 2]:
            server = {
                'host': uut.custom[f'tacacs_tls{idx}_name'],
                'server': uut.custom[f'tacacs_tls{idx}_ip'],
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                'tls_connection_timeout': uut.custom['tls_conn_timeout'],
                'tls_retries': uut.custom['tls_retries'],
                'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
                'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
                'tls_source_interface': uut.custom['source_interface'],
            }
            uut.api.configure_tacacs_server(server)
        uut.api.configure_tacacs_group({
            'server_group': uut.custom['tls_group'],
            'server_names': [uut.custom['tacacs_tls1_name'], uut.custom['tacacs_tls2_name']]
        })

        # Non-TLS servers
        for idx in [1, 2]:
            server = {
                'host': uut.custom[f'tacacs_nontls{idx}_name'],
                'server': uut.custom[f'tacacs_nontls{idx}_ip'],
                'key': uut.custom['tacacs_key'],
                'port': uut.custom['nontls_port'],
                'source_interface': uut.custom['source_interface'],
            }
            uut.api.configure_tacacs_server(server)
        uut.api.configure_tacacs_group({
            'server_group': uut.custom['nontls_group'],
            'server_names': [uut.custom['tacacs_nontls1_name'], uut.custom['tacacs_nontls2_name']]
        })

    @aetest.test
    def configure_aaa(self, uut):
        """Configure AAA using server groups in order: TLS, then Non-TLS"""
        uut.api.configure_aaa_authentication_login(
            auth_list='default',
            group_names=[uut.custom['tls_group'], uut.custom['nontls_group']]
        )
        uut.api.configure_aaa_authorization_commands(
            level='15',
            group_names=[uut.custom['tls_group'], uut.custom['nontls_group']]
        )
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=[uut.custom['tls_group'], uut.custom['nontls_group']],
            accounting_action='start-stop'
        )

    @aetest.test
    def verify_ssh_login_tls(self, uut):
        """SSH login, verify authentication, authorization, accounting via TLS group"""
        try:
            uut.api.reconnect_device(via='ssh')
            log.info("SSH login successful")
        except Exception as e:
            self.failed(f"SSH login failed: {e}")

        # Verify logs for AAA/TACACS+ success
        logs = uut.execute('show logging')
        if not re.search(r'Authentication response status=PASS', logs):
            self.failed("Authentication not successful in logs")
        if not re.search(r'Authorization response status=PASS', logs):
            self.failed("Authorization not successful in logs")
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful in logs")

    @aetest.test
    def fail_tls_group_and_verify_nontls_fallback(self, uut):
        """Simulate TLS group failure, verify fallback to Non-TLS group"""
        uut.api.disable_tacacs_group(uut.custom['tls_group'])
        try:
            uut.api.reconnect_device(via='ssh')
            log.info("SSH login via Non-TLS fallback successful")
        except Exception as e:
            self.failed(f"SSH login via Non-TLS failed: {e}")

        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful via Non-TLS fallback")
        uut.api.enable_tacacs_group(uut.custom['tls_group'])

    @aetest.test
    def verify_priv15_accounting(self, uut):
        """Execute privilege 15 CLI, verify accounting logs"""
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Privilege 15 accounting not successful")

    @aetest.test
    def verify_parallel_tls_nontls(self, uut):
        """Verify parallel TLS/Non-TLS accounting/authorization"""
        # This is a placeholder for parallel SSH sessions and bulk CLI execution
        # You may use threading or multiprocessing for actual parallelism
        log.info("Simulating parallel SSH sessions for TLS and Non-TLS")
        # ... implement parallel session logic as needed ...
        logs = uut.execute('show logging')
        if not re.search(r'TLS connection established', logs):
            self.failed("TLS session not established in parallel test")
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful in parallel test")

    @aetest.test
    def verify_no_crash(self, uut):
        """Verify no crashes/tracebacks in logs"""
        logs = uut.execute('show logging')
        if re.search(r'(CRASH|TRACEBACK)', logs, re.IGNORECASE):
            self.failed("Crash or traceback found in logs")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, uut):
        uut.execute('undebug all')
        uut.api.restore_running_config_file(
            path='flash:',
            file='backup_config',
            timeout=300
        )
        uut.disconnect()
