import random, string, sys
import requests

class MailcowHelper:
    def __init__(self, host, apiKey):
        self._host = host
        self._apiKey = apiKey

    def edit_user(self, email, active=None, name=None):
        attr = {}
        if (active is not None):
            attr['active'] = 1 if active else 0
        if (name is not None):
            attr['name'] = name

        json_data = {
            'items': [email],
            'attr': attr
        }

        self._post_request('api/v1/edit/mailbox', json_data)


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

        req = requests.post(api_url, headers=headers, json=json_data)
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
        req = requests.get(requestUrl, headers=headers)
        rsp = req.json()
        req.close()
        
        if not (isinstance(rsp, dict) or isinstance(rsp, list)):
            sys.exit(f"API {url}: got response of a wrong type")

        return rsp


    def _delete_user(self, email):
        json_data = [email]

        self._post_request('api/v1/delete/mailbox', json_data)