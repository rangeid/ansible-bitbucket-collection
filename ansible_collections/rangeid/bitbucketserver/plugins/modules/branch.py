#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2023, Angelo Conforti (angeloxx@angeloxx.it)

from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule
import requests
import json

__metaclass__ = type


DOCUMENTATION = """
---
module: branch
author:
    - "Angelo Conforti (@angeloxx)"
description: Perform branch management on Bibbucket Server
module: branch
options:
  server:
    description:
    - The Bitbucket URL in the format https://<server> or
      https://<server>/<context>
    type: url
    required: true
  project:
    description:
    - The project name, usually 2-4 letters
    type: str
    required: true
  repository:
    description:
    - The repository name, inside the project and without the ".git" extension
    type: str
    required: true
  username:
    description:
    - The Bitbucket user with branch creation and deletion rights
    type: str
    required: true
  password:
    description:
    - The Bitbucket user's password
    type: str
    required: true
  branch:
    description:
    - The new branch name
    type: str
    required: true
  from_branch:
    description:
    - The origin branch name
    type: str
    required: true
  action:
    description:
    - The performed action
    type: choices
    choices:
    - create
    - delete
    default: create
    required: false
"""


def main():
    argument_spec = dict(
        server=dict(required=True, type="str"),
        project=dict(required=True, type="str"),
        repository=dict(required=True, type="str"),
        username=dict(required=True, type="str"),
        password=dict(required=True, type="str", no_log=True),
        branch=dict(required=True, type="str"),
        from_branch=dict(default="master", type="str"),
        action=dict(default="create", type="str", choices=['create', 'delete'])
    )

    module = AnsibleModule(
        argument_spec=argument_spec
    )

    server = module.params.get("server")
    project = module.params.get("project")
    repository = module.params.get("repository")
    branch_to = module.params.get("branch")
    branch_from = module.params.get("from_branch")
    username = module.params.get("username")
    password = module.params.get("password")
    action = module.params.get("action")

    module.run_command_environ_update = dict(
        LANG="C.UTF-8", LC_ALL="C.UTF-8",
        LC_MESSAGES="C.UTF-8", LC_CTYPE="C.UTF-8"
    )
    result = dict(changed=False)

    if not server.startswith("https://"):
        module.fail_json('Server must be https://<servername>')

    if action == 'create':
        data = {
            "name": branch_to,
            "startPoint": branch_from
        }

        try:
            url = f'{server}/rest/branch-utils/1.0/projects/{project}/repos/{repository}/branches'
            response = requests.post(url, auth=(username, password), json=data)

            if response.status_code == 401:
                module.fail_json(msg=f"Access denied for user {username}, verify username and password")
            if response.status_code == 403:
                module.fail_json(msg=f"Access denied for user {username}")

            if response.ok:
                result['changed'] = True
            else:
                error_data = json.loads(response.content.decode('utf-8'))
                module.fail_json(msg=f"Error creating new branch: {error_data['errors'][0]['message']}")
        except requests.exceptions.RequestException as e:
            module.fail_json(msg=f"Request error: {e}")

    if action == 'delete':
        data = {
            "name": branch_to,
        }

        try:
            url = f'{server}/rest/branch-utils/1.0/projects/{project}/repos/{repository}/branches'
            response = requests.delete(url, auth=(username, password), json=data)

            if response.status_code == 401:
                module.fail_json(msg=f"Access denied for user {username}, verify username and password")
            if response.status_code == 403:
                module.fail_json(msg=f"Access denied for user {username}")

            if response.ok:
                result['changed'] = True
            else:
                error_data = json.loads(response.content.decode('utf-8'))
                module.fail_json(msg=f"Error deleting branch: {error_data['errors'][0]['message']}")
        except requests.exceptions.RequestException as e:
            module.fail_json(msg=f"Request error: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
