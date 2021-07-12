# How the sync works
- Script talks to AD via ldap and to Mailcow via https

## Syncing Workflow
- Use one query to get all users of all schools -> ad.users
```
(|(sophomorixRole=student)(sophomorixRole=teacher)(sophomorixRole=schooladministrator))
```

- Use one query to get all projects and classes -> ad.lists
```
(|(sophomorixType=adminclass)(sophomorixType=project))
```
 
- Use one api request to get all active domains -> mailcow.domains.current
```
/api/v1/get/domain/all
```

- Use one api request to get all active mailboxes -> mailcow.mailboxes.current
```
/api/v1/get/mailbox/all
```

- Use one api request to get all active aliases -> mailcow.aliases.current
```
/api/v1/get/alias/all
```

- Use one api request to get all active filters -> mailcow.filters.current
```
/api/v1/get/filters/all
```

- Walk mailcow.domains.current and:
  - Check if description is "#### managed by linuxmuster.net ####"
    - Yes: add to mailcow.domains.managed and mailcow.domains.kill

- Walk mailcow.mailboxes.current and:
  - Check if the mailbox domain is in mailcow.domains.managed
    - Yes: add to mailcow.mailboxes.managed and mailcow.mailboxes.kill

- Walk mailcow.aliases.current and:
  - Check if the alias domain is in mailcow.domains.managed
    - Yes: add to mailcow.aliases.managed and mailcow.aliases.kill

- Walk mailcow.filters.current and:
  - Check if the filter domain is in mailcow.domains.managed
    - Yes: add to mailcow.filters.managed and mailcow.filters.kill

- Walk ad.users and:
  - Check if maildomain is in mailcow.domains.managed 
    - Yes: remove it from mailcow.domains.kill
    - No: Check if maildomain is in mailcow.domains.current
      - Yes: skip this user
      - No: If domain is not in mailcow.domains.add, append it
  - Check if user exists in mailcow.mailboxes.current
    - Yes: remove user from mailcow.mailboxes.kill and Check if user is identical to AD user
      - Yes: continue
      - No: add user to mailcow.users.update
    - No: add user to mailcow.users.add
  - Check if the user has any aliases
    - Yes: Check if the users mail exists in mailcow.aliases.managed
      - Yes: Check if all necessary alias addresses are in place
        - Yes: continue
        - No: add to mailcow.aliases.update
      - No: add to mailcow.aliases.add

- Walk ad.lists and:
  - Use a query to get all members of this list:
  ```
  memberof:1.2.840.113556.1.4.1941:={List DN}
  ```
  - Check maildomain (same as for users)
  - Check mailbox (same as for users)

- mailcow.domains.add now contains all new domains
- mailcow.domains.kill now contains all deleted domains

- mailcow.users.kill now contains all deleted users
- mailcow.users.add now contains all new users
- mailcow.users.update now contains all changed users

- mailcow.aliases.kill now contains all deleted aliases
- mailcow.aliases.add now contains all new aliases
- mailcow.aliases.update now contains all changed aliases

- Sync to mailcow
 - Add all domains from mailcow.domains.add
 - Update all domains from mailcow.domains.update
 - Delete all mailboxes from mailcow.users.kill
 - Add all mailboxes from mailcow.users.add
 - Update all mailboxes from mailcow.users.update
 - Delete all aliases from aliases.users.kill
 - Add all aliases from aliases.users.add
 - Update all aliases from aliases.users.update
 - Delete all domains from mailcow.domains.kill