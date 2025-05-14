import logging
from pyats import aetest
from pyats.log.utils import banner

logger = logging.getLogger(__name__)

class CommonSetup(aetest.CommonSetup):
    """Common setup tasks for the test script"""
    
    @aetest.subsection
    def connect_to_device(self, testbed):
        """Connect to the device"""
        self.device = testbed.devices['vwlc-ksukulka']  # Use the correct device name
        logger.info("Connecting to the device via Telnet...")
        self.device.connect(via='telnet')  # Use Telnet explicitly
        logger.info("Connection successful.")
        
    @aetest.subsection
    def initialize_variables(self):
        """Initialize device variables"""
        logger.info("Retrieving self-signed trustpoint name...")
        try:
            cert_output = self.device.execute("show crypto pki certificates pem | sec self")
            self.parent.parameters['client_trustpoint'] = cert_output.split("------Trustpoint: ")[1].split("------")[0].strip()
            logger.info(f"Trustpoint retrieved: {self.parent.parameters['client_trustpoint']}")
        except IndexError:
            self.failed("Failed to retrieve trustpoint name from device output.")

class ConfigureTacacsServers(aetest.Testcase):
    """Configure TACACS servers with non-TLS configurations"""

    @aetest.setup
    def enable_debugs(self, testbed):
        """Enable required debugs"""
        logger.info("Enabling TACACS debugs")
        device = testbed.devices['vwlc-ksukulka']
        debug_commands = [
            "debug tacacs authentication",
            "debug tacacs events"
        ]
        for cmd in debug_commands:
            device.execute(cmd)

    @aetest.test
    def configure_tacacs_servers(self, testbed):
        """Configure TACACS servers"""
        logger.info("Configuring TACACS servers")
        device = testbed.devices['vwlc-ksukulka']
        try:
            for server_num in [1, 2]:
                server_name = device.custom[f'tac_nontls_server{server_num}']
                server_ip = device.custom[f'nontls_server_ip{server_num}']
                
                config = [
                    f"tacacs server {server_name}",
                    f" address ipv4 {server_ip}"
                ]
                device.configure(config)
        except KeyError as e:
            self.failed(f"Missing required custom attribute: {e}")
        except Exception as e:
            self.failed(f"Failed to configure TACACS servers: {e}")

    @aetest.test
    def configure_server_groups(self, testbed):
        """Configure TACACS server groups"""
        logger.info("Configuring TACACS server groups")
        device = testbed.devices['vwlc-ksukulka']
        try:
            # Non-TLS group configuration
            nontls_config = [
                f"aaa group server tacacs+ {device.custom['nontls_group']}",
                f" server name {device.custom['tac_nontls_server1']}",
                f" server name {device.custom['tac_nontls_server2']}"
            ]
            device.configure(nontls_config)
        except KeyError as e:
            self.failed(f"Missing required custom attribute: {e}")
        except Exception as e:
            self.failed(f"Failed to configure server groups: {e}")

    @aetest.test
    def configure_aaa_authentication(self, testbed):
        """Configure AAA authentication with server groups"""
        logger.info("Configuring AAA authentication")
        device = testbed.devices['vwlc-ksukulka']
        try:
            config = [
                "aaa new-model",
                f"aaa authentication login default group {device.custom['nontls_group']}"
            ]
            device.configure(config)
        except KeyError as e:
            self.failed(f"Missing required custom attribute: {e}")
        except Exception as e:
            self.failed(f"Failed to configure AAA authentication: {e}")

class CommonCleanup(aetest.CommonCleanup):
    """Cleanup tasks after test completion"""
    
    @aetest.subsection
    def disable_debugs(self, testbed):
        """Disable all debugs"""
        logger.info("Disabling all debugs")
        testbed.devices['vwlc-ksukulka'].execute("undebug all")
    
    @aetest.subsection
    def cleanup_config(self, testbed):
        """Remove TACACS configuration"""
        logger.info("Removing TACACS configuration")
        device = testbed.devices['vwlc-ksukulka']
        try:
            # Remove server groups
            device.configure([
                f"no aaa group server tacacs+ {device.custom['nontls_group']}"
            ])
            
            # Remove individual servers
            for server_num in [1, 2]:
                server_name = device.custom[f'tac_nontls_server{server_num}']
                device.configure(f"no tacacs server {server_name}")
        except KeyError as e:
            logger.error(f"Missing custom attribute during cleanup: {e}")
        except Exception as e:
            logger.error(f"Failed to remove TACACS configuration: {e}")

    @aetest.subsection
    def disconnect(self, testbed):
        """Disconnect from device"""
        logger.info("Disconnecting from the device")
        testbed.devices['vwlc-ksukulka'].disconnect()

if __name__ == '__main__':
    aetest.main()
