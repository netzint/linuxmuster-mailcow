import math

class TemporaryObjectListStorage:
    primaryKey = "INVALID"

    def __init__(self):
        self._current = {}
        self._managed = {}
        self._addQueue = {}
        self._updateQueue = {}
        self._killQueue = {}

        self._primaryKey = self.primaryKey

    def loadRawData(self, rawData):
        for element in rawData:
            self._current[element[self._primaryKey]] = element
            if self._checkElementValidity(element):
                self._managed[element[self._primaryKey]] = element
                self._killQueue[element[self._primaryKey]] = element

    def addElement(self, element, elementId):
        """
        This function safely adds an element:
        - If it exists and is unchanged, it removes it from the kill queue
        - If it exists and has changed, it adds it to the update queue
        - If it is unmanaged, it retruns false
        - If it does not exist, it adds it to the add queue
        """
        if elementId in self._managed:
            if elementId in self._killQueue: 
                del self._killQueue[elementId]

            if self._checkElementChanges(element, elementId): 
                self._updateQueue[elementId] = element
                
        elif elementId in self._current:
            return False

        elif elementId not in self._addQueue:
            self._addQueue[elementId] = element

        return True

    def getQueueAsList(self, queue):
        elementList = []
        for key, value in queue.items():
            elementList.append(value)
        return elementList

    def addQueue(self):
        return self.getQueueAsList(self._addQueue)


    def updateQueue(self):
        queue = []
        for key, value in self._updateQueue.items():
            queue.append({
            "attr": value,
            "items": [key]
        })
        return queue


    def killQueue(self):
        return self.getQueueAsList(self._killQueue)

    def queuesAreEmpty(self):
        return len(self._killQueue) == 0 and len(self._addQueue) == 0 and len(self._updateQueue) == 0

    def getQueueCountsString(self, descriptor):
        return f"Going to add {len(self._addQueue)} {descriptor}, update {len(self._updateQueue)} {descriptor} and kill {len(self._killQueue)} {descriptor}"

    def _checkElementChanges(self, element, elementId):
        """
        Checks if an element has changed
        :returns: True if changed, False if not
        """
        currentElement = self._managed[elementId]

        for key, value in element.items():
            if self._checkElementValueDelta(key, currentElement, value):
                #currentValue = "" if key not in currentElement else currentElement[key]
                #print(f"Found delta in {key}. Current: {currentValue} new: {value}")
                return True

        return False

    def _checkElementValueDelta(self, key, currentElement, newValue):
        return key not in currentElement or currentElement[key] != newValue

    def _checkElementValidity(self, element):
        return True

    def _convertBytesToMebibytes(self, byteSize):
        byteSize = int(byteSize)
        if byteSize == 0:
            return 0

        p = math.pow(1024, 2) # 2 stands for mebibyte
        s = round(byteSize / p, 2)
        return int(s)

class DomainListStorage(TemporaryObjectListStorage):
    primaryKey = "domain_name"
    validityCheckDescription = "#### managed by linuxmuster ####"

    def killQueue(self):
        return list(map(lambda x: x["domain_name"], super().killQueue()))

    def _checkElementValueDelta(self, key, currentElement, newValue):
        ignoreKeys = ["domain", "restart_sogo"]
        # For some stupid reason mailcow decided to use different keys in POST and GET
        getKeyNames = {
            "maxquota": "max_quota_for_mbox",
            "defquota": "def_quota_for_mbox",
            "quota": "max_quota_for_domain",
            "mailboxes": "max_num_mboxes_for_domain",
            "aliases": "max_num_aliases_for_domain"
        }
        quotaKeyNames = ["max_quota_for_mbox", "def_quota_for_mbox", "max_quota_for_domain"]

        if key in getKeyNames:
            key = getKeyNames[key]

        if key in ignoreKeys:
            return False
        elif key in quotaKeyNames:
            # The quota is given in bytes by mailcow, but we have mebibytes
            currentQuota = self._convertBytesToMebibytes(currentElement[key])
            newQuota = int(newValue)
            #print(f"Current {key}: {currentQuota} new: {newQuota} raw: {currentElement[key]}")
            return currentQuota != newQuota
        else:
            return super()._checkElementValueDelta(key, currentElement, newValue)

    def _checkElementValidity(self, element):
        return element["description"] == self.validityCheckDescription

class MailboxListStorage(TemporaryObjectListStorage):
    primaryKey = "username"

    def __init__(self, domainListStorage):
        super().__init__()
        self._domainListStorage = domainListStorage

    def killQueue(self):
        return list(map(lambda x: x["username"], super().killQueue()))

    def _checkElementValueDelta(self, key, currentElement, newValue):
        ignoreKeys = ["password", "password2"]
        if key in ignoreKeys:
            return False
        elif key not in currentElement:
            return True
        elif key == "quota":
            # The quota is given in bytes by mailcow, but we have mebibytes
            currentQuota = self._convertBytesToMebibytes(currentElement[key])
            newQuota = int(newValue)
            #print(f"Current quota: {currentQuota} new: {newQuota}")
            return currentQuota != newQuota
        else:
            return super()._checkElementValueDelta(key, currentElement, newValue)

    def _checkElementValidity(self, element):
        return element["domain"] in self._domainListStorage._managed

class AliasListStorage(TemporaryObjectListStorage):
    primaryKey = "address"

    def __init__(self, domainListStorage):
        super().__init__()
        self._domainListStorage = domainListStorage

    def killQueue(self):
        return list(map(lambda x: x["id"], super().killQueue()))

    def _checkElementValidity(self, element):
        return element["domain"] in self._domainListStorage._managed

class FilterListStorage(TemporaryObjectListStorage):
    primaryKey = "username"

    def __init__(self, domainListStorage):
        super().__init__()
        self._domainListStorage = domainListStorage

    def killQueue(self):
        return list(map(lambda x: x["id"], super().killQueue()))

    def updateQueue(self):
        queue = []
        for key, value in self._updateQueue.items():
            filterId = self._managed[key]["id"]
            queue.append({
            "attr": value,
            "items": [filterId]
        })
        return queue

    def _checkElementValidity(self, element):
        domain = element["username"].split("@")[-1]
        return domain in self._domainListStorage._managed and element["filter_type"] == "prefilter" and element["active"] == 1