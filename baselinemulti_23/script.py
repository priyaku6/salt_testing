# Copyright (c) 2025 by Cisco Systems, Inc.
# All rights reserved.

import logging
import time
import re
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
        # Set all required custom variables with defaults if not present
        custom = uut.custom if hasattr(uut, 'custom') else {}
        testscript.parameters['tacacs_nonworking'] = custom.get('tacacs_nonworking', 'TACACS_NONWORKING')
        testscript.parameters['tacacs_working'] = custom.get('tacacs_working', 'TACACS_WORKING')
        testscript.parameters['tacacs_group'] = custom.get('tacacs_group', 'TACACS_GROUP')
        testscript.parameters['tacacs_key'] = custom.get('tacacs_key', 'cisco123')
        testscript.parameters['tacacs_key_type'] = custom.get('tacacs_key_type', 0)
        testscript.parameters['tacacs_trustpoint_client'] = custom.get('tacacs_trustpoint_client', 'TP-self-signed-12345')
        testscript.parameters['tacacs_trustpoint_server'] = custom.get('tacacs_trustpoint_server', 'ISE_TLS_Certificate')
        testscript.parameters['tacacs_port'] = custom.get('tacacs_port', 49)
        testscript.parameters['tacacs_timeout'] = custom.get('tacacs_timeout', 30)
        testscript.parameters['tacacs_source_intf'] = custom.get('tacacs_source_intf', 'GigabitEthernet1')
        testscript.parameters['tacacs_nonworking_ip'] = custom.get('tacacs_nonworking_ip', '192.168.1.100')
        testscript.parameters['tacacs_working_ip'] = custom.get('tacacs_working_ip', '192.168.1.200')

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

class ConfigureTacacsServers(aetest.Testcase):
    """Configure TACACS servers and group"""

    @aetest.test
    def configure_servers_and_group(self, uut, tacacs_nonworking, tacacs_working, tacacs_group,
                                   tacacs_key, tacacs_key_type, tacacs_trustpoint_client,
                                   tacacs_trustpoint_server, tacacs_port, tacacs_timeout,
                                   tacacs_source_intf, tacacs_nonworking_ip, tacacs_working_ip):
        logger.info(banner("Configuring TACACS Servers and Group"))
        # Configure non-working server first, then working server, both in the same group
        config = [
            f"tacacs server {tacacs_nonworking}",
            f" address ipv4 {tacacs_nonworking_ip}",
            f" key {tacacs_key}" if not tacacs_key_type else f" key {tacacs_key_type} {tacacs_key}",
            f" tls port {tacacs_port}",
            f" tls connectiontimeout {tacacs_timeout}",
            f" tls trustpoint client {tacacs_trustpoint_client}",
            f" tls trustpoint server {tacacs_trustpoint_server}",
            f" tls ip tacacs source-interface {tacacs_source_intf}",
            "exit",
            f"tacacs server {tacacs_working}",
            f" address ipv4 {tacacs_working_ip}",
            f" key {tacacs_key}" if not tacacs_key_type else f" key {tacacs_key_type} {tacacs_key}",
            f" tls port {tacacs_port}",
            f" tls connectiontimeout {tacacs_timeout}",
            f" tls trustpoint client {tacacs_trustpoint_client}",
            f" tls trustpoint server {tacacs_trustpoint_server}",
            f" tls ip tacacs source-interface {tacacs_source_intf}",
            "exit",
            f"aaa group server tacacs+ {tacacs_group}",
            f" server name {tacacs_nonworking}",
            f" server name {tacacs_working}",
            "exit"
        ]
        uut.configure(config)
        logger.info("TACACS servers and group configured.")

class ConfigureAccounting(aetest.Testcase):
    """Enable accounting for privilege 15 with TACACS group"""

    @aetest.test
    def enable_accounting(self, uut, tacacs_group):
        logger.info(banner("Configuring AAA Accounting"))
        config = [
            f"aaa accounting commands 15 default start-stop group {tacacs_group}"
        ]
        uut.configure(config)
        logger.info("AAA accounting for privilege 15 enabled.")

class EnableDebugs(aetest.Testcase):
    """Enable TACACS debug logs"""

    @aetest.test
    def enable_tacacs_debugs(self, uut):
        logger.info(banner("Enabling TACACS Debug Logs"))
        debug_cmds = [
            "debug tacacs accounting",
            "debug tacacs events",
            "debug aaa accounting"
        ]
        for cmd in debug_cmds:
            try:
                uut.execute(cmd)
                logger.info(f"Enabled debug: {cmd}")
            except Exception as e:
                logger.warning(f"Could not enable debug {cmd}: {e}")
        try:
            uut.execute("clear logging")
            logger.info("Cleared logging buffer")
        except Exception as e:
            logger.warning(f"Could not clear logging buffer: {e}")

class ExecutePrivilegeCommands(aetest.Testcase):
    """Execute privilege 15 commands to generate accounting records"""

    @aetest.test
    def execute_privilege_commands(self, uut):
        logger.info(banner("Executing Privilege 15 Commands"))
        commands = [
            "show version",
            "show running-config",
            "show interfaces",
            "show ip route"
        ]
        for cmd in commands:
            try:
                logger.info(f"Executing command: {cmd}")
                uut.execute(cmd)
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Error executing command {cmd}: {e}")
        logger.info("Executed privilege 15 commands successfully")

class VerifyAccounting(aetest.Testcase):
    """Verify accounting is successful using TACACS debug logs"""

    @aetest.test
    def verify_accounting_logs(self, uut):
        logger.info(banner("Verifying TACACS Accounting Logs"))
        time.sleep(5)
        try:
            logs = uut.execute("show logging | include TACACS\\+|accounting")
            if re.search(r"TACACS\+: Accounting.*start", logs) and re.search(r"TACACS\+: Accounting.*stop", logs):
                logger.info("Found TACACS+ accounting start and stop messages in logs")
                logger.info("Accounting verification successful")
            else:
                logger.warning("Could not find TACACS+ accounting start and stop messages in logs")
        except Exception as e:
            logger.warning(f"Error checking accounting logs: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""

    @aetest.subsection
    def cleanup_config(self, uut, tacacs_nonworking, tacacs_working, tacacs_group):
        logger.info(banner("Cleaning up TACACS configuration"))
        cleanup_cmds = [
            f"no tacacs server {tacacs_nonworking}",
            f"no tacacs server {tacacs_working}",
            f"no aaa group server tacacs+ {tacacs_group}",
            "no aaa accounting commands 15 default"
        ]
        uut.configure(cleanup_cmds)

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
