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

class TacacsTlsTest(aetest.Testcase):
    """Test TACACS+ TLS and non-TLS configuration, authorization, and accounting"""

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
    def step1_configure_tls_server(self, uut):
        """Step 1: Configure one TACACS+ server with TLS"""
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
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def step2_configure_two_tls_servers(self, uut):
        """Step 2: Configure two TACACS+ servers with TLS"""
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
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
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
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def step3_configure_tls_and_non_tls_servers(self, uut):
        """Step 3: Configure one TLS and one non-TLS TACACS+ server"""
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
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
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
                'single_connection': True
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def step4_configure_tls_group(self, uut):
        """Step 4: Configure two TLS servers in one group"""
        group_name = uut.custom['tacacs_group_name']
        uut.api.configure_tacacs_group({'server_group': group_name, 'server_name': uut.custom['tacacs_server1_name']})
        uut.api.configure_tacacs_group({'server_group': group_name, 'server_name': uut.custom['tacacs_server2_name']})

    @aetest.test
    def step5_configure_fqdn_tls_server(self, uut):
        """Step 5: Configure a TACACS+ server using FQDN and TLS"""
        server_configs = [
            {
                'host': uut.custom['tacacs_fqdn_name'],
                'timeout': uut.custom.get('tacacs_timeout', 10),
                'key_type': uut.custom.get('tacacs_key_type', 7),
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tacacs_fqdn'],
                'address_type': 'hostname',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                'tls_connection_timeout': uut.custom['tls_connection_timeout'],
                'tls_retries': uut.custom['tls_retries'],
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def step6_configure_tls_server(self, uut):
        """Step 6: Configure a TACACS+ server and enable TLS"""
        # This is similar to step1, but can be used for a different server if needed
        server_configs = [
            {
                'host': uut.custom['tacacs_server3_name'],
                'timeout': uut.custom.get('tacacs_timeout', 10),
                'key_type': uut.custom.get('tacacs_key_type', 7),
                'key': uut.custom['tacacs_key'],
                'server': uut.custom['tacacs_server3_ip'],
                'address_type': 'ipv4',
                'single_connection': True,
                'tls_port': uut.custom['tls_port'],
                'tls_idle_timeout': uut.custom['tls_idle_timeout'],
                'tls_connection_timeout': uut.custom['tls_connection_timeout'],
                'tls_retries': uut.custom['tls_retries'],
                'tls_trustpoint_client': self.parent.parameters['self_cert'],
                'tls_trustpoint_server': uut.custom['tls_trustpoint_server'],
                'tls_source_interface': uut.custom['source_interface'],
                'tls_ip_tacacs_source_interface': uut.custom['source_interface']
            }
        ]
        uut.api.configure_tacacs_server(uut, server_configs)

    @aetest.test
    def configure_aaa(self, uut):
        """Configure AAA using the server group"""
        group_name = uut.custom['tacacs_group_name']
        uut.api.configure_aaa_authentication_login(auth_list='default', auth_type='', group_name=group_name)
        uut.api.configure_aaa_authorization_commands(level='15', level_name='default', level_action='', group_name=group_name)
        uut.api.configure_aaa_accounting_commands(accounting_level='15', accounting_name='default', group='group', group_name=group_name, accounting_action='start-stop')

    @aetest.test
    def verify_ssh_login_authorization_accounting(self, uut):
        """Verify SSH login, authorization, and accounting"""
        try:
            uut.api.reconnect_device(via='ssh_tacacs')
            log.info("SSH login successful")
        except Exception as e:
            self.failed(f"SSH login failed: {str(e)}")

        try:
            uut.api.clear_logging()
            uut.execute('show users')
            # Try privilege 15 command
            uut.execute('show running-config')
            # Try bulk privilege 15 commands
            for _ in range(5):
                uut.execute('show version')
            # Verify accounting logs
            uut.api.verify_pattern_in_show_logging(pattern_list=[
                'AAA/ACCT.*Accounting response status = SUCCESS'
            ])
            log.info("TACACS+ accounting successful")
        except Exception as e:
            self.failed(f"Failed to verify accounting: {str(e)}")

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
