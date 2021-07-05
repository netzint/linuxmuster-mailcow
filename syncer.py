import sys, os, string, time, datetime, logging
import templateHelper

from mailcowHelper import MailcowHelper
from ldapHelper import LdapHelper

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%d.%m.%y %H:%M:%S', level=logging.INFO)

class LinuxmusterMailcowSyncer:
    def __init__(self):
        self._config = self._readConfig()

        templateHelper.applyAllTemplates(self._config)

        self._mailcow = MailcowHelper(
            self._config['API_HOST'],
            self._config['API_KEY']
            )
        self._ldap = LdapHelper(
            self._config['LDAP_URI'], 
            self._config['LDAP_BIND_DN'], 
            self._config['LDAP_BIND_DN_PASSWORD'], 
            self._config['LDAP_BASE_DN']
            )

    def sync(self):
        while (True):
            self._sync()
            interval = int(self._config['SYNC_INTERVAL'])
            logging.info(f"Sync finished, sleeping {interval} seconds before next cycle")
            time.sleep(interval)

    def _sync(self):

        ret, adUsers = self._ldap.search(
            "(|(sophomorixRole=student)(sophomorixRole=teacher))",
            ["mail", "proxyAddresses", "sophomorixStatus"]
        )

        if not ret:
            return False

        ret, adLists = self._ldap.search(
            "(|(sophomorixType=adminclass)(sophomorixType=project))",
            ["mail"]
        )

        if not ret:
            return False

        

        print("AdUsers: ", adUsers)
        print("AdLists: ", adLists)

        return


        ret, ldap_results = self._ldap.search( 
                    self._config['LDAP_FILTER'],
                    ['userPrincipalName', 'cn', 'userAccountControl']
                    )

        ldap_results = map(lambda x: (
            x['userPrincipalName'],
            x['cn'],
            False if int(x['userAccountControl']) & 0b10 else True), ldap_results)

        for (email, ldap_name, ldap_active) in ldap_results:
            (api_user_exists, api_user_active, api_name) = self._mailcow.check_user(email)

            unchanged = True

            if not api_user_exists:
                self._mailcow.add_user(email, ldap_name, ldap_active)
                (api_user_exists, api_user_active, api_name) = (True, ldap_active, ldap_name)
                logging.info (f"Added Mailcow user: {email} (Active: {ldap_active})")
                unchanged = False

            if api_user_active != ldap_active:
                self._mailcow.edit_user(email, active=ldap_active)
                logging.info (f"{'Activated' if ldap_active else 'Deactived'} {email} in Mailcow")
                unchanged = False

            if api_name != ldap_name:
                self._mailcow.edit_user(email, name=ldap_name)
                logging.info (f"Changed name of {email} in Mailcow to {ldap_name}")
                unchanged = False

            if unchanged:
                logging.info (f"Checked user {email}, unchanged")

    def _readConfig(self):
        required_config_keys = [
            'LDAP_MAILCOW_LDAP_URI', 
            'LDAP_MAILCOW_LDAP_BASE_DN',
            'LDAP_MAILCOW_LDAP_BIND_DN', 
            'LDAP_MAILCOW_LDAP_BIND_DN_PASSWORD',
            'LDAP_MAILCOW_API_HOST', 
            'LDAP_MAILCOW_API_KEY', 
            'LDAP_MAILCOW_SYNC_INTERVAL'
        ]

        config = {}

        for config_key in required_config_keys:
            if config_key not in os.environ:
                sys.exit (f"Required environment value {config_key} is not set")

            config[config_key.replace('LDAP_MAILCOW_', '')] = os.environ[config_key]

        if 'LDAP_MAILCOW_LDAP_FILTER' in os.environ and 'LDAP_MAILCOW_SOGO_LDAP_FILTER' not in os.environ:
            sys.exit('LDAP_MAILCOW_SOGO_LDAP_FILTER is required when you specify LDAP_MAILCOW_LDAP_FILTER')

        if 'LDAP_MAILCOW_SOGO_LDAP_FILTER' in os.environ and 'LDAP_MAILCOW_LDAP_FILTER' not in os.environ:
            sys.exit('LDAP_MAILCOW_LDAP_FILTER is required when you specify LDAP_MAILCOW_SOGO_LDAP_FILTER')

        config['LDAP_FILTER'] = os.environ['LDAP_MAILCOW_LDAP_FILTER'] if 'LDAP_MAILCOW_LDAP_FILTER' in os.environ else '(&(objectClass=user)(objectCategory=person))'
        config['SOGO_LDAP_FILTER'] = os.environ['LDAP_MAILCOW_SOGO_LDAP_FILTER'] if 'LDAP_MAILCOW_SOGO_LDAP_FILTER' in os.environ else "objectClass='user' AND objectCategory='person'"

        return config

if __name__ == '__main__':
    syncer = LinuxmusterMailcowSyncer()
    syncer.sync()
