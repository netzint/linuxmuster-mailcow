import sys, os, string, time, datetime
import ldap

import api, templates

import logging
logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%d.%m.%y %H:%M:%S', level=logging.INFO)

def main():    
    global config 
    config = read_config()

    templates.applyAllTemplates(config)

    api.api_host = config['API_HOST']
    api.api_key = config['API_KEY']

    while (True):
        sync()
        interval = int(config['SYNC_INTERVAL'])
        logging.info(f"Sync finished, sleeping {interval} seconds before next cycle")
        time.sleep(interval)

def sync():
    ldap_connector = ldap.initialize(f"{config['LDAP_URI']}")
    ldap_connector.set_option(ldap.OPT_REFERRALS, 0)
    ldap_connector.simple_bind_s(config['LDAP_BIND_DN'], config['LDAP_BIND_DN_PASSWORD'])

    ldap_results = ldap_connector.search_s(config['LDAP_BASE_DN'], ldap.SCOPE_SUBTREE, 
                config['LDAP_FILTER'], 
                ['userPrincipalName', 'cn', 'userAccountControl'])

    ldap_results = map(lambda x: (
        x[1]['userPrincipalName'][0].decode(),
        x[1]['cn'][0].decode(),
        False if int(x[1]['userAccountControl'][0].decode()) & 0b10 else True), ldap_results)

    for (email, ldap_name, ldap_active) in ldap_results:
        (api_user_exists, api_user_active, api_name) = api.check_user(email)

        unchanged = True

        if not api_user_exists:
            api.add_user(email, ldap_name, ldap_active)
            (api_user_exists, api_user_active, api_name) = (True, ldap_active, ldap_name)
            logging.info (f"Added Mailcow user: {email} (Active: {ldap_active})")
            unchanged = False

        if api_user_active != ldap_active:
            api.edit_user(email, active=ldap_active)
            logging.info (f"{'Activated' if ldap_active else 'Deactived'} {email} in Mailcow")
            unchanged = False

        if api_name != ldap_name:
            api.edit_user(email, name=ldap_name)
            logging.info (f"Changed name of {email} in Mailcow to {ldap_name}")
            unchanged = False

        if unchanged:
            logging.info (f"Checked user {email}, unchanged")

def read_config():
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
    main()
