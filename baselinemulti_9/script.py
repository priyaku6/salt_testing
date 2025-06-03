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
        testscript.parameters['tacacs_working'] = uut.custom['tacacs_working']
        testscript.parameters['tacacs_nonworking'] = uut.custom['tacacs_nonworking']
        testscript.parameters['tacacs_working_group'] = uut.custom['tacacs_working_group']
        testscript.parameters['tacacs_nonworking_group'] = uut.custom['tacacs_nonworking_group']
        testscript.parameters['tacacs_key'] = uut.custom['tacacs_key']
        testscript.parameters['tacacs_key_type'] = uut.custom['tacacs_key_type']
        testscript.parameters['tacacs_trustpoint_client'] = uut.custom['tacacs_trustpoint_client']
        testscript.parameters['tacacs_trustpoint_server'] = uut.custom['tacacs_trustpoint_server']
        testscript.parameters['tacacs_port'] = uut.custom['tacacs_port']
        testscript.parameters['tacacs_timeout'] = uut.custom['tacacs_timeout']
        testscript.parameters['tacacs_source_intf'] = uut.custom['tacacs_source_intf']
        testscript.parameters['tacacs_working_ip'] = uut.custom['tacacs_working_ip']
        testscript.parameters['tacacs_nonworking_ip'] = uut.custom['tacacs_nonworking_ip']

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

class ConfigureTacacsGroups(aetest.Testcase):
    """Configure TACACS servers and groups"""

    @aetest.test
    def configure_nonworking_server(self, uut, tacacs_nonworking, tacacs_key, tacacs_key_type, tacacs_trustpoint_client, tacacs_trustpoint_server, tacacs_port, tacacs_timeout, tacacs_source_intf, tacacs_nonworking_group, tacacs_nonworking_ip):
        logger.info("Configuring non-working TACACS server and group")
        config = [
            f"tacacs server {tacacs_nonworking}",
            f" address ipv4 {tacacs_nonworking_ip}",
            f" key {tacacs_key} type {tacacs_key_type}",
            f" tls port {tacacs_port}",
            f" tls connectiontimeout {tacacs_timeout}",
            f" tls trustpoint client {tacacs_trustpoint_client}",
            f" tls trustpoint server {tacacs_trustpoint_server}",
            f" tls ip tacacs source-interface {tacacs_source_intf}",
            "exit",
            f"aaa group server tacacs+ {tacacs_nonworking_group}",
            f" server name {tacacs_nonworking}",
            "exit"
        ]
        uut.config('\n'.join(config))

    @aetest.test
    def configure_working_server(self, uut, tacacs_working, tacacs_key, tacacs_key_type, tacacs_trustpoint_client, tacacs_trustpoint_server, tacacs_port, tacacs_timeout, tacacs_source_intf, tacacs_working_group, tacacs_working_ip):
        logger.info("Configuring working TACACS server and group")
        config = [
            f"tacacs server {tacacs_working}",
            f" address ipv4 {tacacs_working_ip}",
            f" key {tacacs_key} type {tacacs_key_type}",
            f" tls port {tacacs_port}",
            f" tls connectiontimeout {tacacs_timeout}",
            f" tls trustpoint client {tacacs_trustpoint_client}",
            f" tls trustpoint server {tacacs_trustpoint_server}",
            f" tls ip tacacs source-interface {tacacs_source_intf}",
            "exit",
            f"aaa group server tacacs+ {tacacs_working_group}",
            f" server name {tacacs_working}",
            "exit"
        ]
        uut.config('\n'.join(config))

class ConfigureAuthentication(aetest.Testcase):
    """Enable login authentication with TACACS groups"""

    @aetest.test
    def configure_login_auth(self, uut, tacacs_nonworking_group, tacacs_working_group):
        logger.info("Configuring login authentication with TACACS groups (non-working first)")
        config = [
            f"aaa authentication login default group {tacacs_nonworking_group} group {tacacs_working_group}"
        ]
        uut.config('\n'.join(config))

class TelnetToDevice(aetest.Testcase):
    """Try telnet to the device using device IP and telnet port"""

    @aetest.test
    def telnet_login(self, testbed, uut):
        logger.info("Attempting telnet login to device")
        telnet_ip = uut.connections['a']['ip']
        telnet_port = uut.connections['a']['port']
        # Attempt telnet connection using pyATS testbed
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
            testbed.parameters['telnet_conn'] = telnet_conn
            logger.info("Telnet connection successful")
        except Exception as e:
            self.failed(f"Telnet connection failed: {e}")

class VerifyLogin(aetest.Testcase):
    """Verify login is successful"""

    @aetest.test
    def verify_login(self, testbed):
        logger.info("Verifying telnet login is successful")
        telnet_conn = testbed.parameters.get('telnet_conn')
        assert telnet_conn and telnet_conn.is_connected, "Telnet login failed"
        logger.info("Telnet login successful via TACACS group failover")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_nonworking, tacacs_working, tacacs_nonworking_group, tacacs_working_group):
        logger.info(banner("Cleaning up TACACS configuration"))
        cleanup_cmds = [
            f"no tacacs server {tacacs_nonworking}",
            f"no tacacs server {tacacs_working}",
            f"no aaa group server tacacs+ {tacacs_nonworking_group}",
            f"no aaa group server tacacs+ {tacacs_working_group}",
            "no aaa authentication login default"
        ]
        uut.config('\n'.join(cleanup_cmds))

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
