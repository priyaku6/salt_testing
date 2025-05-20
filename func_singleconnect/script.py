import logging
import time
import re
from pyats import aetest

log = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect(self, testbed):
        uut = testbed.devices['uut']
        uut.connect(via='ssh')
        self.parent.parameters['uut'] = uut

    @aetest.subsection
    def save_config(self, uut):
        uut.api.copy_running_config_to_flash_memory(timeout=300)

class TacacsNegativeTLSFallback(aetest.Testcase):
    """TLS (not working) + Non-TLS fallback, expect fail, no fallback"""

    @aetest.test
    def configure_servers_and_group(self, uut):
        # TLS server (not working)
        uut.api.configure_tacacs_server({
            'host': uut.custom['tacacs_tls1_name'],
            'server': uut.custom['tacacs_tls1_ip'],  # Intentionally unreachable
            'tls_port': uut.custom['tls_port'],
            'tls_idle_timeout': uut.custom['tls_idle_timeout'],
            'tls_connection_timeout': uut.custom['tls_conn_timeout'],
            'tls_retries': uut.custom['tls_retries'],
            'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
            'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
            'tls_source_interface': uut.custom['source_interface'],
        })
        # Non-TLS server
        uut.api.configure_tacacs_server({
            'host': uut.custom['tacacs_nontls1_name'],
            'server': uut.custom['tacacs_nontls1_ip'],
            'key': uut.custom['tacacs_key'],
            'port': uut.custom['nontls_port'],
            'source_interface': uut.custom['source_interface'],
        })
        # Group: TLS (not working) first, then Non-TLS
        uut.api.configure_tacacs_group({
            'server_group': 'TLS_NonTLS_Group',
            'server_names': [uut.custom['tacacs_tls1_name'], uut.custom['tacacs_nontls1_name']]
        })

    @aetest.test
    def configure_aaa(self, uut):
        uut.api.configure_aaa_authentication_login(
            auth_list='default',
            group_names=['TLS_NonTLS_Group']
        )
        uut.api.configure_aaa_authorization_commands(
            level='15',
            group_names=['TLS_NonTLS_Group']
        )
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=['TLS_NonTLS_Group'],
            accounting_action='start-stop'
        )
        # Enable debugs
        for debug in [
            "debug aaa authorization", "debug tacacs", "debug aaa authentication",
            "debug aaa accounting", "debug ssl openssl errors", "debug ssl openssl states"
        ]:
            uut.execute(debug)

    @aetest.test
    def verify_ssh_login_fails(self, uut):
        try:
            uut.api.reconnect_device(via='ssh')
            self.failed("SSH login succeeded, expected failure")
        except Exception:
            log.info("SSH login failed as expected")
        logs = uut.execute('show logging')
        if re.search(r'NonTLS_Server1', logs):
            self.failed("Non-TLS server was triggered, should NOT be triggered")
        else:
            log.info("Non-TLS server not triggered as expected")

    @aetest.test
    def verify_authorization_fails(self, uut):
        try:
            uut.execute('show running-config')
            self.failed("Authorization succeeded, expected failure")
        except Exception:
            log.info("Authorization failed as expected")
        logs = uut.execute('show logging')
        if re.search(r'Authorization response status=PASS', logs):
            self.failed("Authorization succeeded in logs, expected failure")
        else:
            log.info("Authorization failed in logs as expected")

    @aetest.test
    def verify_accounting_fails(self, uut):
        logs = uut.execute('show logging')
        if re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting succeeded, expected failure")
        else:
            log.info("Accounting failed as expected")

class TacacsTLSNonTLSFallback(aetest.Testcase):
    """TLS group, then Non-TLS group fallback"""

    @aetest.test
    def configure_servers_and_groups(self, uut):
        # Two TLS servers (first unreachable, second reachable)
        for idx in [1, 2]:
            uut.api.configure_tacacs_server({
                'host': uut.custom[f'tacacs_tls{idx}_name'],
                'server': uut.custom[f'tacacs_tls{idx}_ip'],
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                'tls_connection_timeout': uut.custom['tls_conn_timeout'],
                'tls_retries': uut.custom['tls_retries'],
                'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
                'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
                'tls_source_interface': uut.custom['source_interface'],
            })
        uut.api.configure_tacacs_group({
            'server_group': 'TLS_Group',
            'server_names': [uut.custom['tacacs_tls1_name'], uut.custom['tacacs_tls2_name']]
        })
        # Two Non-TLS servers
        for idx in [1, 2]:
            uut.api.configure_tacacs_server({
                'host': uut.custom[f'tacacs_nontls{idx}_name'],
                'server': uut.custom[f'tacacs_nontls{idx}_ip'],
                'key': uut.custom['tacacs_key'],
                'port': uut.custom['nontls_port'],
                'source_interface': uut.custom['source_interface'],
            })
        uut.api.configure_tacacs_group({
            'server_group': 'NonTLS_Group',
            'server_names': [uut.custom['tacacs_nontls1_name'], uut.custom['tacacs_nontls2_name']]
        })

    @aetest.test
    def configure_aaa(self, uut):
        uut.api.configure_aaa_authentication_login(
            auth_list='default',
            group_names=['TLS_Group', 'NonTLS_Group']
        )
        uut.api.configure_aaa_authorization_commands(
            level='15',
            group_names=['TLS_Group', 'NonTLS_Group']
        )
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=['TLS_Group', 'NonTLS_Group'],
            accounting_action='start-stop'
        )
        for debug in [
            "debug aaa authorization", "debug tacacs", "debug aaa authentication",
            "debug aaa accounting", "debug ssl openssl errors", "debug ssl openssl states"
        ]:
            uut.execute(debug)

    @aetest.test
    def verify_ssh_login_and_fallback(self, uut):
        try:
            uut.api.reconnect_device(via='ssh')
            log.info("SSH login successful")
        except Exception as e:
            self.failed(f"SSH login failed: {e}")
        logs = uut.execute('show logging')
        if not re.search(r'NonTLS_Server1|NonTLS_Server2', logs):
            self.failed("Non-TLS fallback not triggered when TLS group failed")
        else:
            log.info("Non-TLS fallback triggered as expected")

    @aetest.test
    def verify_authorization_and_fallback(self, uut):
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'Authorization response status=PASS', logs):
            self.failed("Authorization not successful")
        if not re.search(r'NonTLS_Server1|NonTLS_Server2', logs):
            self.failed("Non-TLS fallback not triggered for authorization")
        else:
            log.info("Non-TLS fallback for authorization as expected")

    @aetest.test
    def verify_accounting_success(self, uut):
        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful")
        else:
            log.info("Accounting successful")

class TacacsNonTLSTLSOrder(aetest.Testcase):
    """Non-TLS group first, then TLS group"""

    @aetest.test
    def configure_aaa(self, uut):
        uut.api.configure_aaa_authentication_login(
            auth_list='default',
            group_names=['NonTLS_Group', 'TLS_Group']
        )
        uut.api.configure_aaa_authorization_commands(
            level='15',
            group_names=['NonTLS_Group', 'TLS_Group']
        )
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=['NonTLS_Group', 'TLS_Group'],
            accounting_action='start-stop'
        )
        for debug in [
            "debug aaa authorization", "debug tacacs", "debug aaa authentication",
            "debug aaa accounting", "debug ssl openssl errors", "debug ssl openssl states"
        ]:
            uut.execute(debug)

    @aetest.test
    def verify_ssh_login_tls_fallback(self, uut):
        try:
            uut.api.reconnect_device(via='ssh')
            log.info("SSH login successful")
        except Exception as e:
            self.failed(f"SSH login failed: {e}")
        logs = uut.execute('show logging')
        if not re.search(r'TLS_Server1|TLS_Server2', logs):
            self.failed("TLS fallback not triggered when Non-TLS group failed")
        else:
            log.info("TLS fallback triggered as expected")

    @aetest.test
    def verify_authorization_success(self, uut):
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'Authorization response status=PASS', logs):
            self.failed("Authorization not successful")
        else:
            log.info("Authorization successful")

    @aetest.test
    def verify_accounting_success(self, uut):
        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful")
        else:
            log.info("Accounting successful")

class TacacsFQDNandIdleTimeout(aetest.Testcase):
    """FQDN, wrong IP, idle timeout, retries, and connection close checks"""

    @aetest.test
    def configure_wrong_and_right_tls(self, uut):
        # Wrong IP server
        uut.api.configure_tacacs_server({
            'host': 'TLS_WrongIP',
            'server': '192.0.2.1',  # Non-existent IP
            'tls_port': uut.custom['tls_port'],
            'tls_idle_timeout': uut.custom['tls_idle_timeout'],
            'tls_connection_timeout': 10,
            'tls_retries': 2,
            'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
            'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
            'tls_source_interface': uut.custom['source_interface'],
        })
        # Correct IP server
        uut.api.configure_tacacs_server({
            'host': 'TLS_RightIP',
            'server': uut.custom['tacacs_tls2_ip'],
            'tls_port': uut.custom['tls_port'],
            'tls_idle_timeout': uut.custom['tls_idle_timeout'],
            'tls_connection_timeout': uut.custom['tls_conn_timeout'],
            'tls_retries': uut.custom['tls_retries'],
            'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
            'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
            'tls_source_interface': uut.custom['source_interface'],
        })
        uut.api.configure_tacacs_group({
            'server_group': 'TLS_WrongRight_Group',
            'server_names': ['TLS_WrongIP', 'TLS_RightIP']
        })

    @aetest.test
    def configure_aaa(self, uut):
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=['TLS_WrongRight_Group'],
            accounting_action='start-stop'
        )
        for debug in [
            "debug aaa accounting", "debug tacacs", "debug ssl openssl errors"
        ]:
            uut.execute(debug)

    @aetest.test
    def verify_accounting_fallback(self, uut):
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'TLS_RightIP', logs):
            self.failed("Accounting did not fallback to correct TLS server after wrong IP")
        else:
            log.info("Accounting fallback to correct TLS server as expected")

    @aetest.test
    def idle_timeout_and_connection_close(self, uut):
        # Configure server with idle-timeout 60s
        uut.api.configure_tacacs_server({
            'host': 'TLS_IdleTimeout',
            'server': uut.custom['tacacs_tls2_ip'],
            'tls_port': uut.custom['tls_port'],
            'tls_idle_timeout': 60,
            'tls_connection_timeout': uut.custom['tls_conn_timeout'],
            'tls_retries': uut.custom['tls_retries'],
            'tls_trustpoint_client': uut.custom['tls_client_trustpoint'],
            'tls_trustpoint_server': uut.custom['tls_server_trustpoint'],
            'tls_source_interface': uut.custom['source_interface'],
        })
        uut.api.configure_tacacs_group({
            'server_group': 'TLS_IdleTimeout_Group',
            'server_names': ['TLS_IdleTimeout']
        })
        uut.api.configure_aaa_accounting_commands(
            accounting_level='15',
            group_names=['TLS_IdleTimeout_Group'],
            accounting_action='start-stop'
        )
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful")
        log.info("Waiting 65 seconds for idle timeout...")
        time.sleep(65)
        logs = uut.execute('show logging')
        if not re.search(r'connection.*closed', logs, re.IGNORECASE):
            self.failed("TCP connection not closed after idle timeout")
        uut.execute('show running-config')
        logs = uut.execute('show logging')
        if not re.search(r'Accounting response status = SUCCESS', logs):
            self.failed("Accounting not successful after new connection")
        else:
            log.info("New connection established and accounting successful after idle timeout")

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
