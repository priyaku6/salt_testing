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
        device_name = 'uut' if 'uut' in testbed.devices else next(iter(testbed.devices))
        log.info(f"Connecting to device: {device_name}")
        uut = testbed.devices[device_name]
        uut.connect(via='ssh_login')
        self.parent.parameters['uut'] = uut
    
    @aetest.subsection
    def initialize_variables(self, uut, testbed, testscript):
        testscript.parameters['tacacs_tls1_name'] = uut.custom["tacacs_tls1_name"]
        testscript.parameters['tacacs_tls2_name'] = uut.custom["tacacs_tls2_name"]
        testscript.parameters['tacacs_tls1_ip'] = uut.custom["tacacs_tls1_ip"]
        testscript.parameters['tacacs_tls2_ip'] = uut.custom["tacacs_tls2_ip"]
        testscript.parameters['tls_group'] = uut.custom["tls_group"]
        testscript.parameters['tls_port'] = uut.custom["tls_port"]
        testscript.parameters['tls_idle_timeout'] = uut.custom["tls_idle_timeout"]
        testscript.parameters['tls_conn_timeout'] = uut.custom["tls_conn_timeout"]
        testscript.parameters['tls_retries'] = uut.custom["tls_retries"]
        testscript.parameters['tls_client_trustpoint'] = uut.custom["tls_client_trustpoint"]
        testscript.parameters['tls_server_trustpoint'] = uut.custom["tls_server_trustpoint"]
        
        testscript.parameters['tacacs_nontls1_name'] = uut.custom["tacacs_nontls1_name"]
        testscript.parameters['tacacs_nontls1_ip'] = uut.custom["tacacs_nontls1_ip"]
        testscript.parameters['tacacs_nontls2_name'] = uut.custom["tacacs_nontls2_name"]
        testscript.parameters['tacacs_nontls2_ip'] = uut.custom["tacacs_nontls2_ip"]
        testscript.parameters['nontls_group'] = uut.custom["nontls_group"]
        testscript.parameters['nontls_port'] = uut.custom["nontls_port"]
        testscript.parameters['tacacs_key'] = uut.custom["tacacs_key"]
        testscript.parameters['source_interface'] = uut.custom["source_interface"]
        testscript.parameters['tacacs_timeout'] = uut.custom["tacacs_timeout"]
        testscript.parameters['address_family'] = uut.custom["address_family"]

    @aetest.subsection
    def save_initial_config(self, uut):
        uut.api.copy_running_config_to_flash_memory(timeout=300)
        uut.api.configure_terminal_length(0)

class TacacsMultiScenarioTest(aetest.Testcase):
    @aetest.setup
    def setup(self, uut, tacacs_tls1_name):
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
            # 'debug ssl.openssl states' removed due to invalid input error
        ]
        for debug in debugs:
            try:
                uut.execute(debug)
            except Exception as e:
                log.warning(f"Skipping debug command '{debug}': {e}")

    def _check_accounting_success(self, logs, fail_msg):
        # Accept both common accounting success log patterns
        if re.search(r'Accounting response status\s*=\s*FAILURE', logs, re.IGNORECASE):
            log.error("TACACS+ Accounting FAILURE detected. Please check:\n"
                      "- Server reachability (ping, port open)\n"
                      "- Shared secret/key match\n"
                      "- Server is configured to allow accounting\n"
                      "- Device source-interface is correct\n"
                      "- Server logs for errors")
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed(fail_msg + " (FAILURE detected)")
        if not (re.search(r'Received accounting response with status\s*PASS', logs, re.IGNORECASE) or
                re.search(r'Accounting response status\s*=\s*SUCCESS', logs, re.IGNORECASE)):
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed(fail_msg)
        else:
            log.info("Accounting successful")

    @aetest.test
    def step1_tls_and_non_tls_failover(self, uut, tacacs_tls1_name, tacacs_tls2_name, tacacs_tls1_ip, tacacs_tls2_ip, tls_group, tls_port, tls_idle_timeout, tls_conn_timeout, tls_retries, tls_client_trustpoint, tls_server_trustpoint, tacacs_nontls1_name, tacacs_nontls1_ip, tacacs_nontls2_name, tacacs_nontls2_ip, nontls_group, nontls_port, tacacs_key, source_interface, tacacs_timeout, address_family):
        tls_server = {
            'host': tacacs_tls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_tls1_ip,
            'address_type': address_family,
            'single_connection': False,
            'tls_port': tls_port,
            'tls_idle_timeout': tls_idle_timeout,
            'tls_connection_timeout': tls_conn_timeout,
            'tls_retries': tls_retries,
            'tls_trustpoint_client': self.parent.parameters['self_cert'],
            'tls_trustpoint_server': 'TP_TLS_FAULTY',
            'tls_source_interface': source_interface,
        }
        non_tls_server = {
            'host': tacacs_nontls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_nontls1_ip,
            'address_type': address_family,
            'single_connection': False,
        }
        uut.api.configure_tacacs_server([tls_server, non_tls_server])
        uut.api.configure_tacacs_group({'server_group': tls_group, 'server_name': tacacs_tls1_name})
        uut.api.configure_tacacs_group({'server_group': tls_group, 'server_name': tacacs_nontls1_name})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=tls_group)
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=tls_group)
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group= "tacacs+", group_name=tls_group, accounting_action='start-stop')
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("Login successful (failover to Non-TLS)")
        except Exception as e:
            self.failed(f"Login failed: {str(e)}")
        uut.api.clear_logging()
        uut.execute('show users')
        time.sleep(20)  # Increased wait for accounting
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", "\n".join(logs.splitlines()[-50:]))
        self._check_accounting_success(logs, "Accounting not successful on Non-TLS after failover")
        if tacacs_nontls1_ip not in logs:
            log.error("Last 50 log lines:\n%s", "\n".join(logs.splitlines()[-50:]))
            self.failed("Failover to Non-TLS server not observed in logs")
        log.info("Failover and accounting verified")

    @aetest.test
    def step2_tls_and_non_tls_groups(self, uut, tacacs_tls1_name, tacacs_tls2_name, tacacs_tls1_ip, tacacs_tls2_ip, tls_group, tls_port, tls_idle_timeout, tls_conn_timeout, tls_retries, tls_client_trustpoint, tls_server_trustpoint, tacacs_nontls1_name, tacacs_nontls1_ip, tacacs_nontls2_name, tacacs_nontls2_ip, nontls_group, nontls_port, tacacs_key, source_interface, tacacs_timeout, address_family):
        tls_server = {
            'host': tacacs_tls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_tls1_ip,
            'address_type': address_family,
            'single_connection': False,
            'tls_port': tls_port,
            'tls_idle_timeout': tls_idle_timeout,
            'tls_connection_timeout': tls_conn_timeout,
            'tls_retries': tls_retries,
            'tls_trustpoint_client': self.parent.parameters['self_cert'],
            'tls_trustpoint_server': 'TP_TLS_FAULTY',
            'tls_source_interface': source_interface,
        }
        non_tls_server = {
            'host': tacacs_nontls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_nontls1_ip,
            'address_type': address_family,
            'single_connection': False,
        }
        uut.api.configure_tacacs_server([tls_server, non_tls_server])
        uut.api.configure_tacacs_group({'server_group': tls_group, 'server_name': tacacs_tls1_name})
        uut.api.configure_tacacs_group({'server_group': nontls_group, 'server_name': tacacs_nontls1_name})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name= (tls_group + " group " + nontls_group))
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name= (tls_group + " group " + nontls_group))
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name= (tls_group + " group " + nontls_group), accounting_action='start-stop')
        uut.api.clear_logging()
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            uut.api.configure_terminal_length(0)
            uut.api.configure_terminal_width(0)
            log.info("Login successful (GROUP failover to Non-TLS GROUP)")
        except Exception as e:
            self.failed(f"Login failed: {str(e)}")
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        self._check_accounting_success(logs, "Accounting not successful on Non-TLS after group failover")
        log.info("Group failover and accounting verified")

    @aetest.test
    def step3_single_tls_server(self, uut, tacacs_tls1_name, tacacs_tls2_name, tacacs_tls1_ip, tacacs_tls2_ip, tls_group, tls_port, tls_idle_timeout, tls_conn_timeout, tls_retries, tls_client_trustpoint, tls_server_trustpoint, tacacs_nontls1_name, tacacs_nontls1_ip, tacacs_nontls2_name, tacacs_nontls2_ip, nontls_group, nontls_port, tacacs_key, source_interface, tacacs_timeout, address_family):
        tls_server = {
            'host': tacacs_tls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_tls1_ip,
            'address_type': address_family,
            'single_connection': False,
            'tls_port': tls_port,
            'tls_idle_timeout': tls_idle_timeout,
            'tls_connection_timeout': tls_conn_timeout,
            'tls_retries': tls_retries,
            'tls_trustpoint_client': self.parent.parameters['self_cert'],
            'tls_trustpoint_server': tls_server_trustpoint,
            'tls_source_interface': source_interface,
        }
        uut.api.configure_tacacs_server([tls_server])
        uut.api.configure_tacacs_group({'server_group': tls_group, 'server_name': tacacs_tls1_name})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=tls_group)
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=tls_group)
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name=tls_group, accounting_action='start-stop')
        uut.api.clear_logging()
        uut.api.reconnect_device(via='ssh_tacacs')
        uut.api.configure_terminal_length(0)
        uut.api.configure_terminal_width(0)
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        self._check_accounting_success(logs, "Accounting not successful for single TLS server")
        log.info("Single TLS server accounting verified")

    @aetest.test
    def step4_single_non_tls_server(self, uut, tacacs_tls1_name, tacacs_tls2_name, tacacs_tls1_ip, tacacs_tls2_ip, tls_group, tls_port, tls_idle_timeout, tls_conn_timeout, tls_retries, tls_client_trustpoint, tls_server_trustpoint, tacacs_nontls1_name, tacacs_nontls1_ip, tacacs_nontls2_name, tacacs_nontls2_ip, nontls_group, nontls_port, tacacs_key, source_interface, tacacs_timeout, address_family):
        non_tls_server = {
            'host': tacacs_nontls1_name,
            'timeout': tacacs_timeout,
            'key_type': 0,
            'key': tacacs_key,
            'server': tacacs_nontls1_ip,
            'address_type': address_family,
            'single_connection': False,
        }
        uut.api.configure_tacacs_server([non_tls_server])
        uut.api.configure_tacacs_group({'server_group': nontls_group, 'server_name': tacacs_nontls1_name})
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=nontls_group)
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=nontls_group)
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name=nontls_group, accounting_action='start-stop')
        uut.api.clear_logging()
        uut.api.reconnect_device(via='ssh_tacacs')
        uut.api.configure_terminal_length(0)
        uut.api.configure_terminal_width(0)
        time.sleep(10)
        logs = uut.execute('show logging')
        log.info("Collected logs:\n%s", logs)
        self._check_accounting_success(logs, "Accounting not successful for only Non-TLS server")
        log.info("Only Non-TLS server accounting verified")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup(self, uut):
        uut.execute('undebug all')
        uut.api.restore_running_config_file(path='flash:', file='backup_config', timeout=300)
        uut.disconnect()
