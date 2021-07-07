from pathlib import Path
import logging, os

def applyAllTemplates(config, dockerapi=None):
    files = [
        'dovecot/ldap/passdb.conf',
        'dovecot/extra.conf',
        'sogo/plist_ldap'
    ]

    configChanged = True
    for file in files:
        thisConfigChanged = _applyTemplate(file, config)
        configChanged = configChanged and thisConfigChanged

    if configChanged and dockerapi:
        logging.info("One or more config files have been changed, restarting dovecot-mailcow and sogo-mailcow now!")
        dockerapi.restartContainer("sogo-mailcow")
        dockerapi.restartContainer("dovecot-mailcow")
    elif not dockerapi:
        logging.info("One or more config files have been changed, please make sure to restart dovecot-mailcow and sogo-mailcow!")

def _applyTemplate(filePath, config):

    configFilePath = f"conf/{filePath}"
    templateFilePath = f"templates/{filePath}"

    with open(templateFilePath) as f:
        templateData = f.read()

    templateVariables = {
        "ldapUri": config['LDAP_URI'],
        "ldapBaseDn": config['LDAP_BASE_DN'],
        "ldapBindDn": config['LDAP_BIND_DN'],
        "ldapBindPassword": config['LDAP_BIND_DN_PASSWORD'],
        "ldapUserFilter": config['LDAP_USER_FILTER'],
        "ldapSogoUserFilter": config['LDAP_SOGO_USER_FILTER']
    }
    
    for key, value in templateVariables.items():
        templateData = templateData.replace(f"@@{key}@@", value)

    if os.path.isfile(configFilePath):
        with open(configFilePath) as f:
            oldFileContents = f.read()

        if oldFileContents.strip() == templateData.strip():
            logging.info(f"Config file {configFilePath} unchanged")
            return False

        backupIndex = 1
        backupFile = f"{configFilePath}.linuxmuster_mailcow_bak"
        while os.path.exists(backupFile):
            backupFile = f"{configFilePath}.linuxmuster_mailcow_bak.{backupIndex}"
            backupIndex += 1

        os.rename(configFilePath, backupFile)
        logging.info(f"Backed up {configFilePath} to {backupFile}")

    Path(os.path.dirname(configFilePath)).mkdir(parents=True, exist_ok=True)

    print(templateData, file=open(configFilePath, 'w'))
    
    logging.info(f"Saved generated config file to {configFilePath}")
    return True