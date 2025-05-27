import logging
import time
import re
from pyats import aetest

log = logging.getLogger(__name__)

def get_custom(uut, key, default=None):
    return uut.custom.get(key, default)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_to_devices(self, testbed):
        uut = testbed.devices['vwlc-ksukulka']
        uut.connect(via='a')
        self.parent.parameters['uut'] = uut

    @aetest.subsection
    def save_initial_config(self, uut):
        uut.api.copy_running_config_to_flash_memory(timeout=300)
        uut.api.configure_terminal_length(0)

class TacacsMultiScenarioTest(aetest.Testcase):
    @aetest.setup
    def setup(self, uut):
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
            "debug ssl openssl errors",
        ]
        for debug in debugs:
            try:
                uut.execute(debug)
            except Exception as e:
                log.warning(f"Skipping debug command '{debug}': {e}")

    def _check_accounting_success(self, logs, fail_msg):
        if re.search(r'Accounting response status\s*=\s*FAILURE', logs, re.IGNORECASE):
            log.error("TACACS+ Accounting FAILURE detected. Please check:\n"
                      "- Server reachability (ping, port open)\n"
                      "- Shared secret/key match\n"
                      "- Server is configured to allow accounting\n"
                      "- Device source-interface is correct\n"
                      "- Server logs for errors")
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed(fail_msg + " (FAILURE detected)")
        if not (re.search(r'TACACS\+ Accounting response status\s*=\s*SUCCESS', logs, re.IGNORECASE) or
                re.search(r'Accounting Response:\s*PASS', logs, re.IGNORECASE)):
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed(fail_msg)

    @aetest.test
    def step1_tls_and_non_tls_failover(self, uut):
        tls_server = {
            'host': 'TAC',
            'timeout': 10,
            'key_type': 0,
            'key': 'key_tls',
            'server': '10.76.239.74',
            'address_type': 'ipv4',
            'single_connection': True,
            'tls_port': 6049,
            'tls_idle_timeout': 61,
            'tls_connection_timeout': 32,
            'tls_retries': 2,
            'tls_trustpoint_client': self.parent.parameters['self_cert'],
            'tls_trustpoint_server': 'TP_TLS',
            'tls_source_interface': 'GigabitEthernet1',
        }
        non_tls_server = {
            'host': 'TAC2',
            'timeout': 10,
            'key_type': 0,
            'key': 'key_nontls',
            'server': '10.76.239.47',
            'address_type': 'ipv4',
            'single_connection': True,
        }
        uut.api.configure_tacacs_server([tls_server, non_tls_server])
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC'})
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC2'})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TAC_GRP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TAC_GRP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TAC_GRP', accounting_action='start-stop')
        try:
            uut.api.reconnect_device(via='a')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("Login successful (failover to Non-TLS)")
        except Exception as e:
            self.failed(f"Login failed: {str(e)}")
        uut.api.clear_logging()
        uut.execute('show users')
        time.sleep(20)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", "\n".join(logs.splitlines()[-50:]))
        self._check_accounting_success(logs, "Accounting not successful on Non-TLS after failover")
        if 'TAC2' not in logs:
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed("Failover to Non-TLS server not observed in logs")
        log.info("Failover and accounting verified")

    @aetest.test
    def step2_tls_and_non_tls_groups(self, uut):
        tls_servers = [
            {
                'host': 'TAC',
                'timeout': 10,
                'key_type': 0,
                'key': 'key_tls',
                'server': '10.76.239.74',
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': 6049,
                'tls_idle_timeout': 61,
                'tls_connection_timeout': 32,
                'tls_retries': 2,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': 'TP_TLS',
                'tls_source_interface': 'GigabitEthernet1',
            }
        ]
        non_tls_servers = [
            {
                'host': 'TAC2',
                'timeout': 10,
                'key_type': 0,
                'key': 'key_nontls',
                'server': '10.76.239.47',
                'address_type': 'ipv4',
                'single_connection': True,
            }
        ]
        uut.api.configure_tacacs_server(tls_servers + non_tls_servers)
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC'})
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC2'})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TAC_GRP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TAC_GRP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TAC_GRP', accounting_action='start-stop')
        uut.api.clear_logging()
        uut.api.reconnect_device(via='a')
        uut.api.configure_terminal_length(0)
        uut.api.configure_terminal_width(0)
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        if not re.search(r'TACACS\+ Accounting response status\s*=\s*SUCCESS', logs, re.IGNORECASE):
            self.failed("Accounting not successful after group failover")
        if 'TAC2' not in logs:
            self.failed("Failover to Non-TLS group not observed in logs")
        log.info("Group failover and accounting verified")

    @aetest.test
    def step3_single_tls_server(self, uut):
        tls_server = {
            'host': 'TAC',
            'timeout': 10,
            'key_type': 0,
            'key': 'key_tls',
            'server': '10.76.239.74',
            'address_type': 'ipv4',
            'single_connection': True,
            'tls_port': 6049,
            'tls_idle_timeout': 61,
            'tls_connection_timeout': 32,
            'tls_retries': 2,
            'tls_trustpoint_client': self.parent.parameters['self_cert'],
            'tls_trustpoint_server': 'TP_TLS',
            'tls_source_interface': 'GigabitEthernet1',
        }
        uut.api.configure_tacacs_server([tls_server])
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC'})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TAC_GRP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TAC_GRP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TAC_GRP', accounting_action='start-stop')
        uut.api.clear_logging()
        uut.api.reconnect_device(via='a')
        uut.api.configure_terminal_length(0)
        uut.api.configure_terminal_width(0)
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        if not re.search(r'TACACS\+ Accounting response status\s*=\s*SUCCESS', logs, re.IGNORECASE):
            self.failed("Accounting not successful for single TLS server")
        log.info("Single TLS server accounting verified")

    @aetest.test
    def step4_single_non_tls_server(self, uut):
        non_tls_server = {
            'host': 'TAC2',
            'timeout': 10,
            'key_type': 0,
            'key': 'key_nontls',
            'server': '10.76.239.47',
            'address_type': 'ipv4',
            'single_connection': True,
        }
        uut.api.configure_tacacs_server([non_tls_server])
        uut.api.configure_tacacs_group({'server_group': 'TAC_GRP', 'server_name': 'TAC2'})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name='TAC_GRP')
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name='TAC_GRP')
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name='TAC_GRP', accounting_action='start-stop')
        uut.api.clear_logging()
        uut.api.reconnect_device(via='a')
        uut.api.configure_terminal_length(0)
        uut.api.configure_terminal_width(0)
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        if not re.search(r'TACACS\+ Accounting response status\s*=\s*SUCCESS', logs, re.IGNORECASE):
            self.failed("Accounting not successful for single Non-TLS server")
        log.info("Single Non-TLS server accounting verified")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, uut):
        uut.execute('undebug all')
        uut.api.restore_running_config_file(path='flash:', file='backup_config', timeout=300)
        uut.disconnect()
