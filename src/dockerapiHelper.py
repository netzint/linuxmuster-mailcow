import random, string, sys, logging, requests, urllib3

class DockerapiHelper:
    def __init__(self, host):
        self._host = host
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def waitForContainersToBeRunning(self, containersToCkeck):
        logging.info("Waiting for containers to be fully running:")
        for container in containersToCkeck:
            logging.info(f"    * {container}")
        while True:
            containers = self.getAllContainers()
            containersChecked = 0
            allContainersRunning = True
            for id, container in containers.items():
                try:
                    thisContainerName = container["Config"]["Labels"]["com.docker.compose.service"]
                except KeyError:
                    continue
                if thisContainerName in containersToCkeck:
                    allContainersRunning = allContainersRunning and container["State"]["Running"]
                    containersChecked += 1
            
            if containersChecked == len(containersToCkeck) and allContainersRunning:
                break
        
        logging.info("All containers running")

    def getAllContainers(self):
        status, containers = self._getRequest("json")
        if status == 200:
            return containers
        return None

    def getContainerId(self, containerName):
        container = self.getContainerByName(containerName)
        if "Id" in container:
            return container["Id"]
        return None

    def getContainerByName(self, containerName):
        containers = self.getAllContainers()
        for id, container in containers.items():
            try:
                thisContainerName = container["Config"]["Labels"]["com.docker.compose.service"]
            except KeyError:
                continue
            if thisContainerName == containerName:
                return container
        return None

    def restartContainer(self, containerName):
        print(f"Restarting container {containerName} ... ", end='', flush=True)
        container = self.getContainerByName(containerName)
        
        if not container:
            print("ERROR getting container details")
            return False

        if container["State"]["Running"]:
            status, data = self._postRequest(f"{container['Id']}/restart")
        elif container["State"]["Paused"] or container ["State"]["Dead"]:
            status, data = self._postRequest(f"{container['Id']}/start")
        elif container["State"]["Restarting"]:
            print("already restarting.")
            return True
        else:
            print("not restartable")
            return False

        if status == 200:
            print("OK")
            return True
        else:
            print(f"ERROR: {status}")
            return False

    def _postRequest(self, url):
        api_url = f"{self._host}/containers/{url}"
        headers = {'Content-type': 'text/html; charset=utf-8'}

        req = requests.post(api_url, headers=headers, verify=False)
        req.close()

        return req.status_code, req.text

    def _getRequest(self, url):
        requestUrl = f"{self._host}/containers/{url}"
        headers = {'Content-type': 'text/html; charset=utf-8'}
        req = requests.get(requestUrl, headers=headers, verify=False)
        req.close()
        
        return req.status_code, req.json()