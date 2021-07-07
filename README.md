# linuxmuster-mailcow

Integration of Mailcow for Linuxmuster.net

* [How does it work](#how-does-it-work)
* [Usage](#usage)
* [Limitations](#limitations)
  * [WebUI and EAS authentication](#webui-and-eas-authentication)
* [Disclaimer](#disclaimer)

## How does it work

A python script periodically syncs all linuxmuster accounts to mailcow. It also automatically creates aliases for user proxyAddress, projects and classes.  
Sogo and dovecot are configured automatically to authenticate against LDAP.  
More details about the sync workflow can be found in SyncWorkflow.md

## Usage

1. Create a file called `docker-compose.override.yml` in your mailcow directory with the following content:

    ```yaml
    version: '2.1'
    services:
        linuxmuster-mailcow:
            image: linuxmuster/linuxmuster-mailcow
            container_name: mailcowcustomized_linuxmuster-mailcow
            depends_on:
                - nginx-mailcow
                - dockerapi-mailcow
            volumes:
                - ./data/conf/dovecot:/conf/dovecot:rw
                - ./data/conf/sogo:/conf/sogo:rw
            environment:
                - LINUXMUSTER_MAILCOW_LDAP_URI=ldap://10.0.0.1
                - LINUXMUSTER_MAILCOW_LDAP_BASE_DN=DC=linuxmuster,DC=lan
                - LINUXMUSTER_MAILCOW_LDAP_BIND_DN=CN=global-binduser,OU=Management,OU=GLOBAL,DC=linuxmuster,DC=lan
                - LINUXMUSTER_MAILCOW_LDAP_BIND_DN_PASSWORD=<YOUR-PASSWORD>
                - LINUXMUSTER_MAILCOW_API_KEY=<YOUR-API-KEY>
                - LINUXMUSTER_MAILCOW_SYNC_INTERVAL=300
            networks:
            mailcow-network:
                aliases:
                - linuxmuster
    ```

3. Configure environmental variables:

    * `LDAP-LINUXMUSTER_MAILCOW_LDAP_URI` - Uri of the Linuxmuster.net server (must be reachable from within the container). The URIs are in syntax `protocol://host:port`. For example `ldap://localhost` or `ldaps://secure.domain.org`
    * `LINUXMUSTER_MAILCOW_LDAP_BASE_DN` - base DN of the AD
    * `LINUXMUSTER_MAILCOW_LDAP_BIND_DN` - bind DN of a special LDAP account that will be used to browse for users
    * `LINUXMUSTER_MAILCOW_LDAP_BIND_DN_PASSWORD` - password for bind DN account
    * `LINUXMUSTER_MAILCOW_API_KEY` - mailcow API key (read/write)
    * `LINUXMUSTER_MAILCOW_SYNC_INTERVAL` - interval in seconds between LDAP synchronizations
    * **Optional**  Only use these if you know what you are doing! They are not required for normal operation!
        * `LDAP-MAILCOW_API_URI` - mailcow API uri.
        ' `LINUXMUSTER_MAILCOW_DOCKERAPI_URI` - dockerapi API uri.

4. Start additional container: `docker-compose up -d linuxmuster-mailcow`
5. Check logs `docker-compose logs linuxmuster-mailcow`

## Limitations

### WebUI and EAS authentication

This tool enables authentication for Dovecot and SOGo, which means you will be able to log into POP3, SMTP, IMAP, and SOGo Web-Interface. **You will not be able to log into mailcow UI or EAS using your LDAP credentials by default.**

As a workaround, you can hook IMAP authentication directly to mailcow by adding the following code above [this line](https://github.com/mailcow/mailcow-dockerized/blob/48b74d77a0c39bcb3399ce6603e1ad424f01fc3e/data/web/inc/functions.inc.php#L608):

```php
    $mbox = imap_open ("{dovecot:993/imap/ssl/novalidate-cert}INBOX", $user, $pass);
    if ($mbox != false) {
        imap_close($mbox);
        return "user";
    }
```

As a side-effect, It will also allow logging into mailcow UI using mailcow app passwords (since they are valid for IMAP). **It is not a supported solution with mailcow and has to be done only at your own risk!**

## Disclaimer

The inspiration for this from @Programmierus over here: https://github.com/Programmierus/ldap-mailcow
