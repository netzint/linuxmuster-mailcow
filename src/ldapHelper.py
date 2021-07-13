import ldap, logging

class LdapHelper:
    def __init__(self, ldapUri, ldapBindDn, ldapBindPassword, ldapBaseDn):
        self._uri = ldapUri
        self._bindDn = ldapBindDn
        self._bindPassword = ldapBindPassword
        self._baseDn = ldapBaseDn

    def bind(self):
        logging.info("Trying to bind to ldap")
        try:
            self._ldapConnection = ldap.initialize(f"{self._uri}")
            self._ldapConnection.set_option(ldap.OPT_REFERRALS, 0)
            self._ldapConnection.simple_bind_s(self._bindDn, self._bindPassword)
            return True
        except Exception as e:
            logging.critical("!!! Error binding to ldap! {} !!!".format(e))
            return False

    def search(self, filter, attrlist=None):
        if self._ldapConnection == None:
            logging.critical("Cannot talk to LDAP")
            return False, None

        try:
            rawResults = self._ldapConnection.search_s(
                    self._baseDn,
                    ldap.SCOPE_SUBTREE,
                    filter,
                    attrlist
                    )
        except Exception as e:
            logging.critical("Error executing LDAP search!")
            print(e)
            return False, None

        try:
            processedResults =  []

            if len(rawResults) <= 0 or rawResults[0][0] == None:
                return False, None

            for dn, rawResult in rawResults:
                if not dn:
                    continue

                processedResult = {}
                
                for attribute, rawValue in rawResult.items():
                    try:
                        if len(rawValue) == 1:
                            processedResult[attribute] = str(rawValue[0].decode())
                        elif len(rawValue) > 0:
                            processedResult[attribute] = []
                            for rawItem in rawValue:
                                processedResult[attribute].append(str(rawItem.decode()))

                    except UnicodeDecodeError:
                        continue

                processedResults.append(processedResult)
                    
            return True, processedResults

        except Exception as e:
            print(e)
            return False, None
