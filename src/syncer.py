import sys, os, string, time, datetime, logging, coloredlogs, random
import templateHelper

from mailcowHelper import MailcowHelper, MailcowException
from ldapHelper import LdapHelper
from objectStorageHelper import DomainListStorage, MailboxListStorage, AliasListStorage, FilterListStorage
from dockerapiHelper import DockerapiHelper
from requests.exceptions import ConnectionError

coloredlogs.install(level='INFO', fmt='%(asctime)s - [%(levelname)s] %(message)s')

class LinuxmusterMailcowSyncer:

    ldapSogoUserFilter = "(sophomorixRole='student' OR sophomorixRole='teacher' OR sophomorixRole='schooladministrator')"
    ldapUserFilter = "(|(sophomorixRole=student)(sophomorixRole=teacher)(sophomorixRole=schooladministrator))"
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
        self._dockerapi.waitForContainersToBeRunning(["nginx-mailcow", "dockerapi-mailcow", "php-fpm-mailcow", "sogo-mailcow", "dovecot-mailcow"])

        templateHelper.applyAllTemplates(self._config, self._dockerapi)

    def sync(self):
        while (True):
            logging.info("=== Starting sync ===")
            if not self._sync():
                logging.critical("!!! The sync failed, see above errors !!!")
                interval = 30
            else:
                logging.info("=== Sync finished successfully ==")
                interval = int(self._config['SYNC_INTERVAL'])
            
            logging.info(f"sleeping {interval} seconds before next cycle")
            time.sleep(interval)

    def _sync(self):

        logging.info("Step 1: Loading current Data from AD")

        logging.info("    * Binding to ldap")
        if not self._ldap.bind():
            return False

        logging.info("    * Loading users from AD")
        ret, adUsers = self._ldap.search(
            self.ldapUserFilter,
            ["mail", "proxyAddresses", "sophomorixStatus", "sophomorixMailQuotaCalculated", "displayName"]
        )

        if not ret:
            logging.critical("!!! Error getting users from AD !!!")
            return False

        logging.info("    * Loading groups from AD")
        ret, adLists = self._ldap.search(
            self.ldapMailingListFilter,
            ["mail", "distinguishedName", "sophomorixMailList", "sAMAccountName"]
        )

        if not ret:
            logging.critical("!!! Error getting lists from AD !!!")
            return False

        mailcowDomains = DomainListStorage()
        mailcowMailboxes = MailboxListStorage(mailcowDomains)
        mailcowAliases = AliasListStorage(mailcowDomains)
        mailcowFilters = FilterListStorage(mailcowDomains)

        logging.info("Step 2: Loading current Data from Mailcow")
        try:
            rawData = self._mailcow.getAllElementsOfType("domain")
            mailcowDomains.loadRawData(rawData)

            rawData = self._mailcow.getAllElementsOfType("mailbox")
            mailcowMailboxes.loadRawData(rawData)

            rawData = self._mailcow.getAllElementsOfType("alias")
            mailcowAliases.loadRawData(rawData)

            # It is actially "filters" (plural); nobody knows why
            rawData = self._mailcow.getAllElementsOfType("filters")
            mailcowFilters.loadRawData(rawData)
        except MailcowException:
            return False
        except ConnectionError as e:
            logging.error(e)
            logging.critical("!!! A connection error occured, is mailcow still starting up? !!!")
            return False
        except Exception as e:
            logging.exception("An exception occured: ", exc_info=e)
            return False

        logging.info("Step 3: Calculating deltas between AD and Mailcow")

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

            self._addMailbox({
                "mail": mail,
                "sophomorixStatus": "U",
                "sophomorixMailQuotaCalculated": 1,
                "displayName": mailingList["sAMAccountName"] + " (list)"
            }, mailcowMailboxes)

            self._addListFilter(mail, list(map(lambda x: x["mail"], members)), mailcowFilters)

        if mailcowDomains.queuesAreEmpty() and mailcowMailboxes.queuesAreEmpty() and mailcowAliases.queuesAreEmpty() and mailcowFilters.queuesAreEmpty():
            logging.info("    * Everything up-to-date!")
            return True
        else:
            logging.info("* Found deltas:")
            logging.info(f"    * {mailcowDomains.getQueueCountsString('domains')}")
            logging.info(f"    * {mailcowMailboxes.getQueueCountsString('mailboxes')}")
            logging.info(f"    * {mailcowAliases.getQueueCountsString('aliases')}")
            logging.info(f"    * {mailcowFilters.getQueueCountsString('filters')}")

        logging.info("Step 4: Syncing deltas to Mailcow")
        
        try:
            self._mailcow.killElementsOfType("filter", mailcowFilters.killQueue())
            self._mailcow.killElementsOfType("alias", mailcowAliases.killQueue())
            self._mailcow.killElementsOfType("mailbox", mailcowMailboxes.killQueue())
            self._mailcow.killElementsOfType("domain", mailcowDomains.killQueue())

            self._mailcow.addElementsOfType("domain", mailcowDomains.addQueue())
            self._mailcow.updateElementsOfType("domain", mailcowDomains.updateQueue())

            self._mailcow.addElementsOfType("mailbox", mailcowMailboxes.addQueue())
            self._mailcow.updateElementsOfType("mailbox", mailcowMailboxes.updateQueue())

            self._mailcow.addElementsOfType("alias", mailcowAliases.addQueue())
            self._mailcow.updateElementsOfType("alias", mailcowAliases.updateQueue())

            self._mailcow.addElementsOfType("filter", mailcowFilters.addQueue())
            self._mailcow.updateElementsOfType("filter", mailcowFilters.updateQueue())
        except MailcowException:
            return False

        self._ldap.unbind()
        return True

    def _addDomain(self, domainName, mailcowDomains):
        return mailcowDomains.addElement({
            "domain": domainName,
            "defquota": 1,
            "maxquota": self._config['DOMAIN_QUOTA'], 
            "quota": self._config['DOMAIN_QUOTA'],
            "description": DomainListStorage.validityCheckDescription,
            "active": 1,
            "restart_sogo": 1,
            "mailboxes": 10000,
            "aliases": 10000,
            "gal": int(self._config['ENABLE_GAL'])
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

    def _addListFilter(self, listAddress, memberAddresses, mailcowFilters):
        scriptData = "### Auto-generated mailinglist filter by linuxmuster ###\r\n\r\n"
        scriptData += "require \"copy\";\r\n\r\n"
        for memberAddress in memberAddresses:
            scriptData += f"redirect :copy \"{memberAddress}\";\r\n"
        scriptData += "\r\ndiscard;stop;"
        mailcowFilters.addElement({
            'active': 1,
            'username': listAddress,
            'filter_type': 'prefilter',
            'script_data': scriptData,
            'script_desc': f"Auto-generated mailinglist filter for {listAddress}"
        }, listAddress)

    def _readConfig(self):
        requiredConfigKeys = [
            'LINUXMUSTER_MAILCOW_LDAP_URI', 
            'LINUXMUSTER_MAILCOW_LDAP_BASE_DN',
            'LINUXMUSTER_MAILCOW_LDAP_BIND_DN', 
            'LINUXMUSTER_MAILCOW_LDAP_BIND_DN_PASSWORD',
            'LINUXMUSTER_MAILCOW_API_KEY', 
            'LINUXMUSTER_MAILCOW_SYNC_INTERVAL',
            'LINUXMUSTER_MAILCOW_DOMAIN_QUOTA',
            'LINUXMUSTER_MAILCOW_ENABLE_GAL'
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
            logging.info("    * {:25}: {}".format(key, value))

        return config

if __name__ == '__main__':
    try:
        syncer = LinuxmusterMailcowSyncer()
        syncer.sync()
    except KeyboardInterrupt:
        pass
