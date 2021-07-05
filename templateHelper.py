from string import Template
from pathlib import Path

import logging, os

def applyAllTemplates(config):
    files = [
        'dovecot/ldap/passdb.conf',
        'dovecot/extra.conf',
        'sogo/plist_ldap'
    ]

    configChanged = True
    for file in files:
        thisConfigChanged = _applyTemplate(file, config)
        configChanged = configChanged and thisConfigChanged

    if configChanged:
        logging.info("One or more config files have been changed, please make sure to restart dovecot-mailcow and sogo-mailcow!")

def _applyTemplate(filePath, config):

    configFilePath = f"conf/{filePath}"
    templateFilePath = f"templates/{filePath}"

    with open(templateFilePath) as f:
        templateData = Template(f.read())

    newFileContents = templateData.substitute(
        ldap_uri=config['LDAP_URI'], 
        ldap_base_dn=config['LDAP_BASE_DN'],
        ldap_bind_dn=config['LDAP_BIND_DN'],
        ldap_bind_dn_password=config['LDAP_BIND_DN_PASSWORD'],
        sogo_ldap_filter=config['SOGO_LDAP_FILTER']
        )

    if os.path.isfile(configFilePath):
        with open(configFilePath) as f:
            oldFileContents = f.read()

        if oldFileContents.strip() == newFileContents.strip():
            logging.info(f"Config file {configFilePath} unchanged")
            return False

        backupIndex = 1
        backupFile = f"{configFilePath}.ldap_mailcow_bak"
        while os.path.exists(backupFile):
            backupFile = f"{configFilePath}.ldap_mailcow_bak.{backupIndex}"
            backupIndex += 1

        os.rename(configFilePath, backupFile)
        logging.info(f"Backed up {configFilePath} to {backupFile}")

    Path(os.path.dirname(configFilePath)).mkdir(parents=True, exist_ok=True)

    print(newFileContents, file=open(configFilePath, 'w'))
    
    logging.info(f"Saved generated config file to {configFilePath}")
    return True