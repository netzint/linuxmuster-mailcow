import random, string, sys, logging
import requests, urllib3

class MailcowException(Exception):
    pass

class MailcowHelper:
    def __init__(self, host, apiKey):
        self._host = host
        self._apiKey = apiKey
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def addElementsOfType(self, elementType, elements):
        self._processElementList(elementType, elements, "api/v1/add", True, "adding")

    def killElementsOfType(self, elementType, elements):
        self._processElementList(elementType, elements, "api/v1/delete", False, "killing")

    def updateElementsOfType(self, elementType, elements):
        self._processElementList(elementType, elements, "api/v1/edit", True, "updating")

    def _processElementList(self, elementType, elements, apiPath, processOneByOne, actionString):
        elementCount = len(elements)
        if elementCount <= 0:
            return

        logging.info(f"    * {actionString} {len(elements)} {elementType}s")

        if not processOneByOne:
            elementCount = 1

        for i in range(elementCount):
            if processOneByOne:
                logging.info(f"        * {actionString} {elementType} {i+1}/{elementCount}")
                res, errorMessage = self._postRequest(f"{apiPath}/{elementType}", elements[i])
            else:
                res, errorMessage = self._postRequest(f"{apiPath}/{elementType}", elements)

            if not res:
                logging.critical(f"!!! Error while {actionString} {elementType}: {elements[i]}")
                logging.critical(f"!!! Error message from server: \"{self._getErrorMessage(errorMessage)}\"!!!")
                raise MailcowException(errorMessage)

    def getAllElementsOfType(self, elementType):
        logging.info(f"    * Loading current {elementType}s from Mailcow")
        res, data = self._getRequest(f"api/v1/get/{elementType}/all")
        if res != 200:
            logging.critical(f"!!! Error getting {elementType}s from Mailcow: {data} !!!")
            raise MailcowException(res)
        return data

    def _postRequest(self, url, json_data):
        api_url = f"{self._host}/{url}"
        headers = {'X-API-Key': self._apiKey, 'Content-type': 'application/json'}

        logging.debug(f"Sending POST with JSON: {json_data}")

        req = requests.post(api_url, headers=headers, json=json_data, verify=False)
        rsp = req.json()
        req.close()

        if isinstance(rsp, list):
            rsp = rsp[0]

        if "type" in rsp and "msg" in rsp:
            if rsp['type'] != 'success':
                return False, rsp['msg']
            else:
                return True, None
        else:
            return False, f"Got malformed response! Is {self._host} a mailcow server?"

    def _getRequest(self, url):
        requestUrl = f"{self._host}/{url}"
        headers = {'X-API-Key': self._apiKey, 'Content-type': 'application/json'}

        logging.debug(f"Sending GET to: {requestUrl}")

        req = requests.get(requestUrl, headers=headers, verify=False)
        rsp = req.json()
        req.close()

        if req.status_code != 200:
            if "type" in rsp and "msg" in rsp:
                return req.status_code, rsp["msg"]
            else:
                return req.status_code, f"Got malformed response! Is {self._host} a mailcow server?"

        return req.status_code, rsp


    def _getErrorMessage(self, error):
        commonErrors = {
            "mailbox_quota_left_exceeded": "The quota of the domain was exeeded, please choose a higher value for LINUXMUSTER_MAILCOW_DOMAIN_QUOTA"
        }
        if error[0] in commonErrors:
            return commonErrors[error[0]]
        else:
            return error