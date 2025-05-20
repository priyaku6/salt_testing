import logging
import time
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    @aetest.subsection
    def connect_device(self, testbed):
        uut = testbed.devices['uut']
        # Use the correct connection name for telnet
        uut.connect(via='telnet', log_stdout=False)
        assert uut.connected, f"Couldn't connect to device {uut}"
        self.parent.parameters['uut'] = uut

class ConfigureTacacs(aetest.Testcase):
    @aetest.test
    def configure_tacacs_server_and_group(self, uut):
        c = uut.custom
        cmds = [
            f"no tacacs server {c['tacacs_server_name']}",
            f"tacacs server {c['tacacs_server_name']}",
            f" address ipv4 {c['tacacs_ip']}",
            f" key cisco123",
            f" source-interface {c['source_interface']}",
            "exit",
            f"no aaa group server tacacs+ {c['tacacs_server_group']}",
            f"aaa group server tacacs+ {c['tacacs_server_group']}",
            f" server name {c['tacacs_server_name']}",
            "exit"
        ]
        uut.configure(cmds)
        logger.info("TACACS server and group configured.")

class EnableDebugs(aetest.Testcase):
    @aetest.test
    def enable_tacacs_and_ssl_debugs(self, uut):
        debug_cmds = [
            "debug tacacs",
            "debug tacacs events",
            "debug tacacs authorization",
            "debug tacacs accounting",
            "debug ip ssh",
            "debug crypto ssl"
        ]
        for cmd in debug_cmds:
            uut.execute(cmd)
        uut.execute("terminal monitor")
        logger.info("TACACS and SSL debugs enabled.")

class ConfigureAAA(aetest.Testcase):
    @aetest.test
    def configure_authorization_accounting(self, uut):
        c = uut.custom
        cmds = [
            "aaa new-model",
            f"aaa authentication login default group {c['tacacs_server_group']} local",
            f"aaa authorization commands 15 default group {c['tacacs_server_group']} local",
            f"aaa accounting commands 15 default start-stop group {c['tacacs_server_group']}",
            "line vty 0 4",
            "login authentication default",
            "exit"
        ]
        uut.configure(cmds)
        logger.info("AAA authorization and accounting configured.")

class BulkPriv15Commands(aetest.Testcase):
    @aetest.test
    def run_bulk_priv15_commands(self, uut):
        c = uut.custom
        commands = [
            "show running-config",
            "show version",
            "show interfaces",
            "show ip route",
            "show logging"
        ]
        iterations = 5
        authz_times = []
        acct_times = []
        for i in range(iterations):
            logger.info(banner(f"Iteration {i+1}"))
            uut.execute("clear logging")
            for cmd in commands:
                start = time.time()
                uut.execute(cmd)
                end = time.time()
                time.sleep(1)
                logs = uut.execute("show logging | include TACACS|Authorization|Accounting")
                if "Authorization" in logs:
                    authz_times.append(end - start)
                if "Accounting" in logs:
                    acct_times.append(end - start)
        avg_authz = sum(authz_times) / len(authz_times) if authz_times else 0
        avg_acct = sum(acct_times) / len(acct_times) if acct_times else 0
        logger.info(f"Average Authorization time: {avg_authz:.3f} seconds")
        logger.info(f"Average Accounting time: {avg_acct:.3f} seconds")
        self.parent.parameters['avg_authz'] = avg_authz
        self.parent.parameters['avg_acct'] = avg_acct

    @aetest.test
    def verify_results(self):
        avg_authz = self.parent.parameters.get('avg_authz', 0)
        avg_acct = self.parent.parameters.get('avg_acct', 0)
        if avg_authz > 0 and avg_acct > 0:
            logger.info(f"Authorization and Accounting successful. Avg Authz: {avg_authz:.3f}s, Avg Acct: {avg_acct:.3f}s")
        else:
            self.failed("Authorization or Accounting did not succeed in any iteration.")

class CommonCleanup(aetest.CommonCleanup):
    @aetest.subsection
    def cleanup_config(self, uut):
        c = uut.custom
        cmds = [
            "no aaa authentication login default",
            "no aaa authorization commands 15 default",
            "no aaa accounting commands 15 default",
            f"no aaa group server tacacs+ {c['tacacs_server_group']}",
            f"no tacacs server {c['tacacs_server_name']}",
            "no aaa new-model"
        ]
        try:
            uut.configure(cmds)
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    @aetest.subsection
    def disconnect_device(self, uut):
        uut.disconnect()

if __name__ == '__main__':
    from pyats.easypy import run
    run(testscript=__file__)
