import sys, os, string, time, datetime, logging, random
import templateHelper

from mailcowHelper import MailcowHelper
from ldapHelper import LdapHelper
from objectStorageHelper import DomainListStorage, MailboxListStorage, AliasListStorage
from dockerapiHelper import DockerapiHelper

logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%d.%m.%y %H:%M:%S', level=logging.INFO)

class LinuxmusterMailcowSyncer:

    ldapSogoUserFilter = "sophomorixRole='student' OR sophomorixRole='teacher'"
    ldapUserFilter = "(|(sophomorixRole=student)(sophomorixRole=teacher))"
    ldapMailingListFilter = "(|(sophomorixType=adminclass)(sophomorixType=project))"
    ldapMailingListMemberFilter = f"(&(memberof:1.2.840.113556.1.4.1941:=@@mailingListDn@@){ldapUserFilter})"

    def __init__(self):
        self._config = self._readConfig()

        self._mailcow = MailcowHelper(
            self._config['API_URI'],
            self._config['API_KEY']
            )
        self._ldap = LdapHelper(
            self._config['LDAP_URI'], 
            self._config['LDAP_BIND_DN'], 
            self._config['LDAP_BIND_DN_PASSWORD'], 
            self._config['LDAP_BASE_DN']
            )

        self._dockerapi = DockerapiHelper(self._config["DOCKERAPI_URI"])

        templateHelper.applyAllTemplates(self._config, self._dockerapi)

    def sync(self):
        while (True):
            self._sync()
            interval = int(self._config['SYNC_INTERVAL'])
            logging.info(f"Sync finished, sleeping {interval} seconds before next cycle")
            time.sleep(interval)

    def _sync(self):

        ret, adUsers = self._ldap.search(
            self.ldapUserFilter,
            ["mail", "proxyAddresses", "sophomorixStatus", "sophomorixMailQuotaCalculated", "displayName"]
        )

        if not ret:
            logging.error("Error getting users from AD")
            return False

        ret, adLists = self._ldap.search(
            self.ldapMailingListFilter,
            ["mail", "distinguishedName", "sophomorixMailList"]
        )

        if not ret:
            logging.error("Error getting lists from AD")
            return False

        mailcowDomains = DomainListStorage()
        mailcowMailboxes = MailboxListStorage(mailcowDomains)
        mailcowAliases = AliasListStorage(mailcowDomains)

        ret, rawData = self._mailcow.getAllEntriesOfType("domain")
        if not ret:
            logging.error("Error getting domains from Mailcow")
            return False
        mailcowDomains.loadRawData(rawData)

        ret, rawData = self._mailcow.getAllEntriesOfType("mailbox")
        if not ret:
            logging.error("Error getting mailboxes from Mailcow")
            return False
        mailcowMailboxes.loadRawData(rawData)

        ret, rawData = self._mailcow.getAllEntriesOfType("alias")
        if not ret:
            logging.error("Error getting aliases from Mailcow")
            return False
        mailcowAliases.loadRawData(rawData)

        for user in adUsers:
            mail = user["mail"]
            maildomain = mail.split("@")[-1]
            aliases = []

            if "proxyAddresses" in user:
                if isinstance(user["proxyAddresses"], list):
                    aliases = user["proxyAddresses"]
                else:
                    aliases = [user["proxyAddresses"]]

            if not self._addDomain(maildomain, mailcowDomains):
                continue

            self._addMailbox(user, mailcowMailboxes)

            if len(aliases) > 0:
                for alias in aliases:
                    self._addAlias(alias, mail, mailcowAliases)

        for mailingList in adLists:
            if not mailingList["sophomorixMailList"] == "TRUE":
                continue
            
            mail = mailingList["mail"]
            maildomain = mail.split("@")[-1]
            ret, members = self._ldap.search(
                self.ldapMailingListMemberFilter.replace("@@mailingListDn@@", mailingList["distinguishedName"]),
                ["mail"]
            )
            
            if not ret:
                continue

            if not self._addDomain(maildomain, mailcowDomains):
                continue

            mailcowGotoString = ""
            for member in members:
                mailcowGotoString += f"{member['mail']},"
            mailcowGotoString = mailcowGotoString[:-1]

            self._addAlias(mail, mailcowGotoString, mailcowAliases)

        #print("mailboxesKill: ", mailcowMailboxes.killQueue())
        #print("mailboxesAdd: ", mailcowMailboxes.addQueue())
        #print("mailboxesUpdate: ", mailcowMailboxes.updateQueue())
        #print("domainsAdd: ", mailcowDomains.addQueue())
        #print("domainsKill: ", mailcowDomains.killQueue())
        #print("domainsUpdate: ", mailcowDomains.updateQueue())
        #print("aliasesAdd: ", mailcowAliases.addQueue())
        #print("aliasesUpdate: ", mailcowAliases.updateQueue())
        #print("aliasesKill: ", mailcowAliases.killQueue())

        self._mailcow.addElementsOfType("domain", mailcowDomains.addQueue())
        self._mailcow.editElementsOfType("domain", mailcowDomains.updateQueue())

        self._mailcow.addElementsOfType("mailbox", mailcowMailboxes.addQueue())
        self._mailcow.killElementsOfType("mailbox", mailcowMailboxes.killQueue())
        self._mailcow.editElementsOfType("mailbox", mailcowMailboxes.updateQueue())

        self._mailcow.addElementsOfType("alias", mailcowAliases.addQueue())
        self._mailcow.killElementsOfType("alias", mailcowAliases.killQueue())
        self._mailcow.editElementsOfType("alias", mailcowAliases.updateQueue())

        self._mailcow.killElementsOfType("domain", mailcowDomains.killQueue())
        return True

    def _addDomain(self, domainName, mailcowDomains):
        return mailcowDomains.addElement({
            "domain": domainName,
            "defquota": 2,
            "maxquota": self._config['DOMAIN_QUOTA'], 
            "quota": self._config['DOMAIN_QUOTA'],
            "description": DomainListStorage.validityCheckDescription,
            "active": 1,
            "restart_sogo": 1,
            "mailboxes": 10000,
            "aliases": 10000
            }, domainName)

    def _addMailbox(self, user, mailcowMailboxes):
        mail = user["mail"]
        domain = mail.split("@")[-1]
        localPart = mail.split("@")[0]
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=20))
        active = 0 if user["sophomorixStatus"] in ["L", "D", "R", "K", "F"] else 1
        return mailcowMailboxes.addElement({
            "domain": domain,
            "local_part": localPart,
            "active": active,
            "quota": user["sophomorixMailQuotaCalculated"],
            "password":password,
            "password2":password,
            "name": user["displayName"]
            }, mail)

    def _addAlias(self, alias, goto, mailcowAliases):
        mailcowAliases.addElement({
            "address": alias,
            "goto": goto,
            "active": 1,
            "sogo_visible":1
            }, alias)
        pass

    def _readConfig(self):
        requiredConfigKeys = [
            'LINUXMUSTER_MAILCOW_LDAP_URI', 
            'LINUXMUSTER_MAILCOW_LDAP_BASE_DN',
            'LINUXMUSTER_MAILCOW_LDAP_BIND_DN', 
            'LINUXMUSTER_MAILCOW_LDAP_BIND_DN_PASSWORD',
            'LINUXMUSTER_MAILCOW_API_KEY', 
            'LINUXMUSTER_MAILCOW_SYNC_INTERVAL',
            'LINUXMUSTER_MAILCOW_DOMAIN_QUOTA'
        ]

        allowedConfigKeys = [
            "LINUXMUSTER_MAILCOW_DOCKERAPI_URI",
            "LINUXMUSTER_MAILCOW_API_URI"
        ]

        config = {
            "LDAP_SOGO_USER_FILTER": self.ldapSogoUserFilter,
            "LDAP_USER_FILTER": self.ldapUserFilter,
            "DOCKERAPI_URI": "https://dockerapi-mailcow",
            "API_URI": "https://nginx-mailcow"
        }

        for configKey in requiredConfigKeys:
            if configKey not in os.environ:
                sys.exit (f"Required environment value {configKey} is not set")
            config[configKey.replace('LINUXMUSTER_MAILCOW_', '')] = os.environ[configKey]

        for configKey in allowedConfigKeys:
            if configKey in os.environ:
                config[configKey.replace('LINUXMUSTER_MAILCOW_', '')] = os.environ[configKey]

        logging.info("CONFIG:")
        for key, value in config.items():
            logging.info("\t* {:25}: {}".format(key, value))
        print()

        return config

if __name__ == '__main__':
    syncer = LinuxmusterMailcowSyncer()
    syncer.sync()
