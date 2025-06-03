
# Copyright (c) 2025 by Cisco Systems, Inc.
# All rights reserved.

import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""

    @aetest.subsection
    def validate_topology(self, testbed):
        logger.info(banner("Validating Topology"))
        if not testbed:
            self.skipped("No testbed was provided")

    @aetest.subsection
    def initialize_variables(self, testbed, testscript):
        logger.info(banner("Variable Initialization..."))
        uut = testbed.devices['uut']
        testscript.parameters['uut'] = uut
        testscript.parameters['tacacs_server'] = uut.custom['tacacs_server']
        testscript.parameters['tacacs_group'] = uut.custom['tacacs_group']
        testscript.parameters['tacacs_key'] = uut.custom['tacacs_key']
        testscript.parameters['tacacs_key_type'] = uut.custom['tacacs_key_type']
        testscript.parameters['tacacs_trustpoint_client'] = uut.custom['tacacs_trustpoint_client']
        testscript.parameters['tacacs_trustpoint_server'] = uut.custom['tacacs_trustpoint_server']
        testscript.parameters['tacacs_port'] = uut.custom['tacacs_port']
        testscript.parameters['tacacs_timeout'] = uut.custom['tacacs_timeout']
        testscript.parameters['tacacs_source_intf'] = uut.custom['tacacs_source_intf']
        testscript.parameters['tacacs_server_ip'] = uut.custom['tacacs_server_ip']

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

class ConfigureISE(aetest.Testcase):
    """Configure ISE to enable TACACS"""

    @aetest.test
    def enable_tacacs(self, uut):
        logger.info("Assuming ISE is already configured to enable TACACS (external step).")
        # If you have CLI/API to enable TACACS on ISE, add it here.

class ConfigureTacacsServerGroup(aetest.Testcase):
    """Configure TACACS server and server group"""

    @aetest.test
    def configure_server_and_group(self, uut, tacacs_server, tacacs_key, tacacs_key_type, tacacs_trustpoint_client, tacacs_trustpoint_server, tacacs_port, tacacs_timeout, tacacs_source_intf, tacacs_group, tacacs_server_ip):
        logger.info("Configuring TACACS server and group")
        config = [
            f"tacacs server {tacacs_server}",
            f" address ipv4 {tacacs_server_ip}",
            f" key {tacacs_key} type {tacacs_key_type}",
            f" tls port {tacacs_port}",
            f" tls connectiontimeout {tacacs_timeout}",
            f" tls trustpoint client {tacacs_trustpoint_client}",
            f" tls trustpoint server {tacacs_trustpoint_server}",
            f" tls ip tacacs source-interface {tacacs_source_intf}",
            "exit",
            f"aaa group server tacacs+ {tacacs_group}",
            f" server name {tacacs_server}",
            "exit"
        ]
        uut.config('\n'.join(config))

class ConfigureAuthorization(aetest.Testcase):
    """Enable Authorization with TACACS group of privilege 15"""

    @aetest.test
    def configure_authorization(self, uut, tacacs_group):
        logger.info("Configuring authorization with TACACS group for privilege 15")
        config = [
            f"aaa authorization commands 15 default group {tacacs_group}"
        ]
        uut.config('\n'.join(config))

class Priv15CommandTest(aetest.Testcase):
    """Try executing any privilege level 15 CLIs on the ssh console"""

    @aetest.test
    def execute_priv15_command(self, uut):
        logger.info("Executing privilege level 15 CLI on SSH console")
        # Example: show running-config (priv 15)
        try:
            output = uut.execute("show running-config")
            logger.info("Command output: %s", output[:200])
            uut.parameters['priv15_output'] = output
        except Exception as e:
            self.failed(f"Failed to execute priv 15 command: {e}")

class Priv15CommandTelnetTest(aetest.Testcase):
    """Try executing any privilege level 15 CLIs on the telnet console"""

    @aetest.test
    def execute_priv15_command_telnet(self, testbed, uut):
        logger.info("Attempting to execute privilege 15 CLI via telnet console")
        telnet_ip = uut.connections['a']['ip']
        telnet_port = uut.connections['a']['port']
        from unicon import Connection
        try:
            telnet_conn = Connection(
                hostname='uut_telnet',
                start=[f'telnet {telnet_ip} {telnet_port}'],
                os=uut.os,
                platform=uut.platform,
                username=uut.credentials['default']['username'],
                password=uut.credentials['default']['password'],
                enable_password=uut.credentials['enable']['password'],
                prompt_recovery=True,
            )
            telnet_conn.connect()
            output = telnet_conn.execute("show running-config")
            testbed.parameters['telnet_conn'] = telnet_conn
            testbed.parameters['priv15_telnet_output'] = output
            logger.info("Telnet privilege 15 command output: %s", output[:200])
        except Exception as e:
            self.failed(f"Telnet privilege 15 command failed: {e}")

class VerifyAuthorization(aetest.Testcase):
    """Verify authorization is successful"""

    @aetest.test
    def verify_authorization(self, uut):
        logger.info("Verifying authorization for privilege 15 command")
        output = uut.parameters.get('priv15_output', '')
        assert 'Current configuration' in output or 'hostname' in output, "Authorization failed: Priv 15 command did not succeed"
        logger.info("Authorization for privilege 15 command is successful")

    @aetest.test
    def verify_authorization_telnet(self, testbed):
        logger.info("Verifying authorization for privilege 15 command via telnet")
        output = testbed.parameters.get('priv15_telnet_output', '')
        assert 'Current configuration' in output or 'hostname' in output, "Authorization failed: Priv 15 command did not succeed via telnet"
        logger.info("Authorization for privilege 15 command via telnet is successful")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_server, tacacs_group):
        logger.info(banner("Cleaning up TACACS configuration"))
        cleanup_cmds = [
            f"no tacacs server {tacacs_server}",
            f"no aaa group server tacacs+ {tacacs_group}",
            "no aaa authorization commands 15 default"
        ]
        uut.config('\n'.join(cleanup_cmds))

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
