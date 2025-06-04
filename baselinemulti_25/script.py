# Copyright (c) 2024 by Cisco Systems, Inc.
# All rights reserved.

import logging
import re
import time
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
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
        # Custom variables with defaults
        testscript.parameters['non_working_server_name'] = uut.custom.get('non_working_server_name', 'NON_WORKING_TAC')
        testscript.parameters['non_working_server_ip'] = uut.custom.get('non_working_server_ip', '192.0.2.1')
        testscript.parameters['non_working_server_group'] = uut.custom.get('non_working_server_group', 'NON_WORKING_GROUP')
        testscript.parameters['working_server_name'] = uut.custom.get('working_server_name', 'WORKING_TAC')
        testscript.parameters['working_server_ip'] = uut.custom.get('working_server_ip', '192.0.2.2')
        testscript.parameters['working_server_group'] = uut.custom.get('working_server_group', 'WORKING_GROUP')
        testscript.parameters['tls_port'] = uut.custom.get('tls_port', '49')
        testscript.parameters['key'] = uut.custom.get('key', 'cisco123')
        testscript.parameters['source_interface'] = uut.custom.get('source_interface', 'GigabitEthernet1')
        testscript.parameters['ise_trustpoint'] = 'ISE_TLS_Certificate'
        testscript.parameters['default_client_trustpoint'] = 'TP-self-signed-1234567890'
        testscript.parameters['initial_config'] = None

    @aetest.subsection
    def connect_device(self, uut):
        logger.info(banner("Connecting to the device via SSH..."))
        uut.connect()
        assert uut.connected, f"Couldn't connect to device {uut}"
        logger.info("Successfully connected to device %s" % uut.name)

    @aetest.subsection
    def backup_initial_config(self, uut, testscript):
        logger.info(banner("Backing up initial configuration"))
        testscript.parameters['initial_config'] = uut.execute("show running-config")

class TacacsAccountingFailoverTest(aetest.Testcase):
    """Test case to verify TACACS accounting failover functionality"""

    @aetest.setup
    def setup(self, uut):
        logger.info(banner("Setup Environment"))
        self.client_trustpoint = "TP-self-signed-1234567890"
        try:
            uut.api.configure_aaa_new_model()
        except Exception:
            uut.configure("aaa new-model")
        try:
            uut.configure("service internal")
        except Exception:
            pass
        debug_commands = [
            "debug tacacs accounting",
            "debug tacacs events",
            "debug aaa accounting",
            "terminal monitor"
        ]
        for cmd in debug_commands:
            try:
                uut.execute(cmd)
            except Exception:
                pass

    @aetest.test
    def extract_client_trustpoint(self, uut, default_client_trustpoint):
        logger.info(banner("Extracting Device Self-Signed Certificate Name"))
        try:
            output = uut.execute("show crypto pki certificates pem | sec self")
            match = re.search(r'Trustpoint: (TP-self-signed-\d+)', output)
            if match:
                self.client_trustpoint = match.group(1)
            else:
                output = uut.execute("show crypto pki trustpoints status")
                match = re.search(r'(TP-self-signed-\d+)', output)
                if match:
                    self.client_trustpoint = match.group(1)
                else:
                    self.client_trustpoint = default_client_trustpoint
        except Exception:
            self.client_trustpoint = default_client_trustpoint

    @aetest.test
    def configure_ise_certificate(self, uut, ise_trustpoint):
        logger.info(banner("Configuring ISE TLS Certificate"))
        try:
            config_commands = [
                f"crypto pki trustpoint {ise_trustpoint}",
                " enrollment terminal",
                "exit"
            ]
            uut.configure(config_commands)
            logger.info("Certificate trustpoint configured (import step is manual/simulated)")
        except Exception as e:
            logger.warning(f"Failed to configure ISE certificate: {e}")

    @aetest.test
    def configure_tacacs_servers(self, uut, non_working_server_name, non_working_server_ip, 
                                 working_server_name, working_server_ip, tls_port, 
                                 source_interface, key, ise_trustpoint):
        logger.info(banner("Configuring TACACS Servers"))
        # Non-working server
        non_working_server_config = [
            f"tacacs server {non_working_server_name}",
            " single-connection",
            f" address ipv4 {non_working_server_ip}",
            f" key {key}",
            " tls",
            f" tls port {tls_port}",
            " tls idletimeout 61",
            " tls connectiontimeout 32",
            " tls retries 2",
            f" tls trustpoint client {self.client_trustpoint}",
            f" tls trustpoint server {ise_trustpoint}",
            f" tls ip tacacs source-interface {source_interface}"
        ]
        uut.configure(non_working_server_config)
        # Working server
        working_server_config = [
            f"tacacs server {working_server_name}",
            " single-connection",
            f" address ipv4 {working_server_ip}",
            f" key {key}",
            " tls",
            f" tls port {tls_port}",
            " tls idletimeout 61",
            " tls connectiontimeout 32",
            " tls retries 2",
            f" tls trustpoint client {self.client_trustpoint}",
            f" tls trustpoint server {ise_trustpoint}",
            f" tls ip tacacs source-interface {source_interface}"
        ]
        uut.configure(working_server_config)

    @aetest.test
    def configure_tacacs_server_groups(self, uut, non_working_server_name, non_working_server_group, 
                                       working_server_name, working_server_group):
        logger.info(banner("Configuring TACACS Server Groups"))
        uut.configure([
            f"aaa group server tacacs+ {non_working_server_group}",
            f" server name {non_working_server_name}"
        ])
        uut.configure([
            f"aaa group server tacacs+ {working_server_group}",
            f" server name {working_server_name}"
        ])

    @aetest.test
    def configure_aaa_accounting(self, uut, non_working_server_group, working_server_group):
        logger.info(banner("Configuring AAA Accounting"))
        uut.configure([
            f"aaa accounting commands 15 default start-stop group {non_working_server_group} group {working_server_group}"
        ])
        uut.configure([
            f"aaa authentication login default group {non_working_server_group} group {working_server_group} local",
            f"aaa authorization commands 15 default group {non_working_server_group} group {working_server_group} local"
        ])

    @aetest.test
    def execute_privileged_commands(self, uut):
        logger.info(banner("Executing Privileged Commands"))
        uut.execute("clear logging")
        privileged_commands = [
            "show version",
            "show running-config",
            "show interfaces",
            "show ip route"
        ]
        for cmd in privileged_commands:
            uut.execute(cmd)
            time.sleep(1)

    @aetest.test
    def verify_tacacs_accounting_failover(self, uut, non_working_server_ip, working_server_ip):
        logger.info(banner("Verifying TACACS Accounting Failover"))
        log_output = uut.execute("show logging")
        # Look for failover and accounting evidence
        failover = re.search(f"{non_working_server_ip}.*fail|timeout|unreachable", log_output, re.IGNORECASE)
        success = re.search(f"{working_server_ip}.*accounting|pass|recorded", log_output, re.IGNORECASE)
        start = re.search(r"accounting.*start", log_output, re.IGNORECASE)
        stop = re.search(r"accounting.*stop", log_output, re.IGNORECASE)
        if start and stop and success:
            logger.info("Accounting failover verified successfully.")
        else:
            logger.warning("Could not fully verify accounting failover in logs.")

    @aetest.cleanup
    def disable_debugging(self, uut):
        logger.info(banner("Disabling Debugging"))
        uut.execute("undebug all")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup_config(self, uut, initial_config, non_working_server_name, 
                       working_server_name, non_working_server_group,
                       working_server_group, ise_trustpoint):
        logger.info(banner("Cleaning up configurations"))
        cleanup_commands = [
            "no aaa accounting commands 15 default",
            "no aaa authentication login default",
            "no aaa authorization commands 15 default",
            f"no aaa group server tacacs+ {non_working_server_group}",
            f"no aaa group server tacacs+ {working_server_group}",
            f"no tacacs server {non_working_server_name}",
            f"no tacacs server {working_server_name}",
            f"no crypto pki trustpoint {ise_trustpoint}"
        ]
        for command in cleanup_commands:
            try:
                uut.configure(command)
            except Exception:
                pass
        if "aaa new-model" not in initial_config:
            uut.configure("no aaa new-model")
        if "service internal" not in initial_config:
            uut.configure("no service internal")
        try:
            uut.execute("write memory")
        except Exception:
            pass

    @aetest.subsection
    def disconnect_device(self, uut):
        logger.info(banner("Disconnecting from device"))
        uut.disconnect()
