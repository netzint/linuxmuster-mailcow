import random, string, sys
import requests, urllib3

class MailcowHelper:
    def __init__(self, host, apiKey):
        self._host = host
        self._apiKey = apiKey
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def addElementsOfType(self, type, elements):
        for element in elements:
            self._post_request(f"api/v1/add/{type}", element)

    def killElementsOfType(self, type, elements):
        self._post_request(f"api/v1/delete/{type}", elements)

    def editElementsOfType(self, type, elements):
        for element in elements:
            self._post_request(f"api/v1/edit/{type}", element)

    def getAllEntriesOfType(self, type):
        rsp = self._getRequest(f"api/v1/get/{type}/all")

        return True, rsp

    def _post_request(self, url, json_data):
        api_url = f"{self._host}/{url}"
        headers = {'X-API-Key': self._apiKey, 'Content-type': 'application/json'}

        print("Sending POST with JSON: ", json_data)

        req = requests.post(api_url, headers=headers, json=json_data, verify=False)
        rsp = req.json()
        req.close()

        if isinstance(rsp, list):
            rsp = rsp[0]

        if not "type" in rsp or not "msg" in rsp:
            sys.exit(f"API {url}: got response without type or msg from Mailcow API")
        
        if rsp['type'] != 'success':
            sys.exit(f"API {url}: {rsp['type']} - {rsp['msg']}")

    def _getRequest(self, url):
        requestUrl = f"{self._host}/{url}"

        headers = {'X-API-Key': self._apiKey, 'Content-type': 'application/json'}
        req = requests.get(requestUrl, headers=headers, verify=False)
        rsp = req.json()
        req.close()
        
        if not (isinstance(rsp, dict) or isinstance(rsp, list)):
            sys.exit(f"API {url}: got response of a wrong type")

        return rsp