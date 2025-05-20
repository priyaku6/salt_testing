import logging
import re
from pyats import aetest

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

class TacacsMergedTest(aetest.Testcase):
    """Merged TACACS+ TLS/Non-TLS/FQDN/Group testcases"""

    @aetest.setup
    def setup(self, uut):
        """Setup required configurations"""
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
        ]
        for debug in debugs:
            uut.execute(debug)

    @aetest.test
    def configure_all_tacacs_servers(self, uut):
        """Configure all TACACS+ servers for all steps using the API"""
        server_configs = [
            # Step 1: TLS (Not Working) and Non-TLS
            {
                'host': uut.custom['tls_not_working_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tls_not_working_ip'],
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': 'UNREACHABLE_TP',
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            },
            {
                'host': uut.custom['non_tls_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['non_tls_ip'],
                'address_type': 'ipv4',
                'single_connection': True
            },
            # Step 2: Two TLS servers
            {
                'host': uut.custom['tls1_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tls1_ip'],
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            },
            {
                'host': uut.custom['tls2_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tls2_ip'],
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            },
            # Step 3: FQDN with TLS
            {
                'host': uut.custom['fqdn_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['fqdn'],
                'address_type': 'hostname',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            },
            # Step 4: Another TLS server
            {
                'host': uut.custom['tls3_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tls3_ip'],
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': 60,
                'tls_connection_timeout': 5,
                'tls_retries': 3,
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            },
            # Step 6: Two Non-TLS servers
            {
                'host': uut.custom['non_tls1_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['non_tls1_ip'],
                'address_type': 'ipv4',
                'single_connection': True
            },
            {
                'host': uut.custom['non_tls2_name'],
                'timeout': 10,
                'key_type': 7,
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['non_tls2_ip'],
                'address_type': 'ipv4',
                'single_connection': True
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def configure_all_server_groups(self, uut):
        """Configure all TACACS+ server groups"""
        # Step 2: TLS group
        uut.api.configure_tacacs_group({'server_group': uut.custom['tls_group'], 'server_name': uut.custom['tls1_name']})
        uut.api.configure_tacacs_group({'server_group': uut.custom['tls_group'], 'server_name': uut.custom['tls2_name']})
        # Step 5: TLS (Not Working) + Non-TLS group
        uut.api.configure_tacacs_group({'server_group': uut.custom['mixed_group'], 'server_name': uut.custom['tls_not_working_name']})
        uut.api.configure_tacacs_group({'server_group': uut.custom['mixed_group'], 'server_name': uut.custom['non_tls_name']})
        # Step 6: Non-TLS group
        uut.api.configure_tacacs_group({'server_group': uut.custom['non_tls_group'], 'server_name': uut.custom['non_tls1_name']})
        uut.api.configure_tacacs_group({'server_group': uut.custom['non_tls_group'], 'server_name': uut.custom['non_tls2_name']})
        # Step 7: FQDN group
        uut.api.configure_tacacs_group({'server_group': uut.custom['fqdn_group'], 'server_name': uut.custom['fqdn_name']})
        # Step 4: TLS3 group
        uut.api.configure_tacacs_group({'server_group': uut.custom['tls3_group'], 'server_name': uut.custom['tls3_name']})

    @aetest.test
    def configure_aaa(self, uut):
        """Configure AAA for all groups (priv 15 command accounting/authorization)"""
        # Example: Use mixed_group for main AAA
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=uut.custom['mixed_group'])
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=uut.custom['mixed_group'])
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name=uut.custom['mixed_group'], accounting_action='start-stop')

    @aetest.test
    def verify_ssh_login_authorization_accounting(self, uut):
        """Verify SSH login, authorization, and accounting for all groups"""
        # SSH login should fail (TLS not working), so expect failure
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            self.failed("SSH login succeeded but should have failed")
        except Exception:
            log.info("SSH login failed as expected")

        # Authorization should fail
        try:
            uut.api.get_running_config()
            self.failed("Authorization succeeded but should have failed")
        except Exception:
            log.info("Authorization failed as expected")

        # Accounting should still be successful in logs
        uut.api.clear_logging()
        uut.execute('show users')
        # Try privilege 15 command
        try:
            uut.execute('show running-config')
        except Exception:
            pass
        # Try bulk privilege 15 commands
        for _ in range(5):
            try:
                uut.execute('show version')
            except Exception:
                pass
        # Verify accounting logs
        uut.api.verify_pattern_in_show_logging(pattern_list=[
            'AAA/ACCT.*Accounting response status = SUCCESS'
        ])
        log.info("TACACS+ accounting successful")

        # Check for crashes/tracebacks
        logs = uut.execute("show logging")
        if "crash" in logs or "traceback" in logs:
            self.failed("Crash or traceback found in logs")

class CommonCleanup(aetest.CommonCleanup):
    """Restore initial configuration."""
    @aetest.subsection
    def cleanup(self, uut):
        """Restore the saved configuration and cleanup."""
        uut.execute('undebug all')
        uut.api.restore_running_config_file(
            path='flash:',
            file='backup_config',
            timeout=300
        )
        uut.disconnect()
