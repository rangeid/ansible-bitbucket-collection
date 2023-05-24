#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: (c) 2023, Angelo Conforti (angeloxx@angeloxx.it)

from __future__ import absolute_import, division, print_function
from ansible.module_utils._text import to_text
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import fetch_url, basic_auth_header
import urllib.parse
import json


__metaclass__ = type


DOCUMENTATION = """
---
module: pullrequest
author:
    - "Angelo Conforti (@angeloxx)"
description: Perform pull-request management on Bibbucket Server
module: pullrequest
options:
  server:
    description:
    - The Bitbucket URL in the format https://<server> or https://<server>/<context>
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
  to_branch:
    description:
    - The source branch
    type: str
    default: master
    required: false
  from_branch:
    description:
    - The destination branch
    type: str
    required: true
  title:
    description:
    - The pull request title, always required to create or find the pull request to approve or merge
    type: str
    required: true
  description:
    description:
    - The pull request description
    type: str
    required: false
  authors:
    description:
    - The pull request author name
    type: str
    required: true
  actions:
    description:
    - The performed action, multiple options are allowed.
    - B(create) will create new PR from from_branch to to_branch with specified title and description
    - B(approve) will approve a PR (but Bitbucket doesn't allow to approve own PR)
    - B(merge) action will merge from_branch to to_branch
    type: list
    elements: str
    required: true
  ignore_existing_on_create:
    description:
    - Don't raise an error if create fails due an existing branch with same source and destination branch
    type: str
    required: true
"""


def getPullRequests(module, result, server, username, password, project_key,
                    repository_slug, title):
    """
    Retrieve a list of pull requests matching the specified parameters.

    :param module: The Ansible module instance.
    :param server: The URL of the Bitbucket server.
    :param username: The username for authentication.
    :param password: The password for authentication.
    :param project_key: The key of the project containing the repository.
    :param repository_slug: The slug of the repository.
    :param title: The title of the pull requests to search for.
    :return: A list of pull requests matching the specified parameters.
    """
    # TODO: page length >= 1000
    title = urllib.parse.quote(title)
    url = f'{server}/rest/api/latest/projects/{project_key}/repos/{repository_slug}/pull-requests?filterText={title}'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': basic_auth_header(username, password)
    }

    response, info = fetch_url(module, url, headers=headers, method='GET',
                               timeout=30)

    if info['status'] == 401:
        module.fail_json(
            msg=f"Access denied for user {username}, verify username and password")
    if info['status'] == 403:
        module.fail_json(msg=f"Access denied for user {username}")

    return json.loads(str(response.read().decode("utf-8")))


def mergePullRequest(module, result, server, username, password, project_key,
                     repository_slug, pull_request_id, version=-1):
    """
    Merge the specified pull request.

    :param module: The Ansible module instance.
    :param server: The URL of the Bitbucket server.
    :param username: The username for authentication.
    :param password: The password for authentication.
    :param project_key: The key of the project containing the repository.
    :param repository_slug: The slug of the repository.
    :param pull_request_id: The ID of the pull request to be merged.
    """
    url = f'{server}/rest/api/1.0/projects/{project_key}/repos/{repository_slug}/pull-requests/{pull_request_id}/merge'
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': basic_auth_header(username, password)
    }

    data = {
        "version": version
    }

    response, info = fetch_url(module, url, headers=headers, method='POST',
                               data=json.dumps(data), timeout=30)

    if info['status'] == 401:
        module.fail_json(
            msg=f"Access denied for user {username}, verify username and password")
    elif info['status'] == 403:
        module.fail_json(msg=f"Access denied for user {username}")
    elif info['status'] == 200:
        result['changed'] = True
        module.warn(f"Pull request {pull_request_id} successfully merged.")
    elif info['status'] == 409:
        error_data = json.loads(info['body'])
        module.fail_json(msg=f"Unable to merge the pull request "
                         f"#{pull_request_id}. {error_data['errors'][0]['message']}",
                         status_code=info['status'])
    else:
        error_data = json.loads(info['body'])
        module.fail_json(
            msg=f"Unable to merge the pull request: {error_data['errors'][0]['message']}")


def deletePullRequest(module, result, server, username, password, project_key,
                      repository_slug, pull_request_id, version=-1): 
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': basic_auth_header(username, password)
    }
    data = {
        "version": version
    }

    # https://developer.atlassian.com/server/bitbucket/rest/v810/api-group-pull-requests/#api-api-latest-projects-projectkey-repos-repositoryslug-pull-requests-pullrequestid-delete
    url = f'{server}/rest/api/latest/projects/{project_key}/repos/{repository_slug}/pull-requests/{pull_request_id}'
    response, info = fetch_url(method="DELETE", module=module, url=url,
                               data=json.dumps(data), headers=headers)
    if info['status'] == 401:
        module.fail_json(
            msg=f"Access denied for user {username}, verify username and password.")
    if info['status'] == 403:
        module.fail_json(msg=f"Access denied for user {username}")
    if info['status'] == 404:
        module.fail_json(msg=f"Pull request #{pull_request_id} doesn't exist.")
    if info['status'] == 204:
        module.warn(f"Pull request #{pull_request_id} deleted.")
        result['changed'] = True
    else:
        error_data = json.loads(info['body'])
        module.fail_json(
            msg=f"Error deleting pull request #{pull_request_id}: {error_data['errors'][0]['message']}",
            return_code=info['status'])


def approvePullRequest(module, result, server, username, password, project_key,
                       repository_slug, pull_request_id):

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': basic_auth_header(username, password)
    }
    data = {
        "user": {
            "name": username
        },
        "approved": True,
        "status": "APPROVED"
    }

    url = f'{server}/rest/api/latest/projects/{project_key}/repos/{repository_slug}/pull-requests/{pull_request_id}/approve'
    response, info = fetch_url(method="POST", module=module, url=url,
                               headers=headers, data=json.dumps(data))

    if info['status'] == 401:
        module.fail_json(
            msg=f"Access denied for user {username}, verify username and password")
    if info['status'] == 403:
        module.fail_json(msg=f"Access denied for user {username}")

    if info['status'] == [200, 201]:
        result['changed'] = True
    else:
        error_data = json.loads(info['body'])
        module.fail_json(
            msg=f"Error approving pull request: {error_data['errors'][0]['message']}")


def createPullRequest(module, result, server, username, password,
                      project_key, repository_slug, title, description,
                      source_branch, destination_branch,
                      ignore_existing_on_create=False):
    """
    Create a pull request on Bitbucket Data Center.

    :param server: The URL of the Bitbucket server.
    :param username: The username for authentication.
    :param password: The password for authentication.
    :param project_key: The key of the project containing the repository.
    :param repository_slug: The slug of the repository.
    :param title: The title of the pull request.
    :param source_branch: The source branch for the pull request.
    :param destination_branch: The destination branch for the pull request.
    :return: The response from the API call.
    """
    url = f"{server}/rest/api/1.0/projects/{project_key}/repos/{repository_slug}/pull-requests"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': basic_auth_header(username, password)
    }
    payload = {
        "title": title,
        "description": description,
        "fromRef": {
            "id": source_branch,
            "repository": {
                "slug": repository_slug,
                "project": {
                    "key": project_key
                }
            }
        },
        "toRef": {
            "id": destination_branch,
            "repository": {
                "slug": repository_slug,
                "project": {
                    "key": project_key
                }
            }
        },
        "locked": False
    }

    response, info = fetch_url(module, url, headers=headers, method='POST',
                               data=json.dumps(payload), timeout=30)
    # Check the response status code
    if info['status'] == 201:
        result['changed'] = True
        module.warn("Pull request successfully created.")
    elif info['status'] == 409:
        if ignore_existing_on_create is True:
            error_data = json.loads(to_text(info['body']))
            module.warn(
                f"{error_data['errors'][0]['message']}. Deleting #{error_data['errors'][0]['existingPullRequest']['id']} as requested.")
            deletePullRequest(module, result, server, username, password, project_key,
                              repository_slug, int(error_data['errors'][0]['existingPullRequest']['id']), int(error_data['errors'][0]['existingPullRequest']['version']))
            createPullRequest(module, result, server, username, password, project_key,
                              repository_slug, title, description,
                              source_branch, destination_branch)
        else:
            error_data = json.loads(info['body'])
            module.fail_json(changed=True,
                             msg=f"{error_data['errors'][0]['message']}")

    else:
        error_data = json.loads(info['body'])
        module.fail_json(
            msg=f"Unable to create the pull request. "
                f"{error_data['errors'][0]['message']}")


def main():
    argument_spec = dict(
        server=dict(required=True, type="str"),
        project=dict(required=True, type="str"),
        repository=dict(required=True, type="str"),
        username=dict(required=True, type="str"),
        password=dict(required=True, type="str", no_log=True),
        to_branch=dict(default="master", type="str"),
        from_branch=dict(type="str"),
        title=dict(required=True, type="str"),
        description=dict(required=False, type="str"),
        author=dict(default="Ansible", type="str"),
        actions=dict(required=True, type="list", choices=[
                     'create', 'approve', 'merge']),
        ignore_existing_on_create=dict(default=False, type="bool",
                                       aliases=["delete_existing_on_create"]),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        # required_together=[("to_branch", "from_branch")],
        #  required_one_of=[("add", "pull", "push")]
    )

    server = module.params.get("server")
    project = module.params.get("project")
    repository = module.params.get("repository")
    branch_to = module.params.get("to_branch")
    branch_from = module.params.get("from_branch")
    title = module.params.get("title")
    description = module.params.get("description")
    ignore_existing_on_create = module.params.get("ignore_existing_on_create")
    actions = module.params.get("actions")
    author = module.params.get("author")
    username = module.params.get("username")
    password = module.params.get("password")

    module.run_command_environ_update = dict(
        LANG="C.UTF-8", LC_ALL="C.UTF-8", LC_MESSAGES="C.UTF-8", LC_CTYPE="C.UTF-8"
    )
    result = dict(changed=False)

    if not server.startswith("https://"):
        module.fail_json('Server must be https://<servername>')

    if "create" in actions:
        try:
            createPullRequest(module, result, server, username, password, project,
                              repository, title, description,
                              branch_from, branch_to,
                              ignore_existing_on_create)
        except Exception as e:
            module.fail_json(msg=f"Create PR request error: {e}")

    if "approve" in actions:
        try:
            prs = getPullRequests(module, result, server, username, password,
                                  project, repository, title)
            mypr = {}
            for pr in prs['values']:
                if (pr['state'] == 'OPEN' and pr['title'] == title and
                    pr['fromRef']['displayId'] == branch_from and
                        pr['toRef']['displayId'] == branch_to):
                    mypr = pr
                    break

            if mypr == {}:
                module.fail_json(
                    msg=f"Unable to find a PR that matches title <{title}>")

            data = {
                "user": {
                    "name": author
                },
                "approved": True,
                "status": "APPROVED"
            }

            url = f'{server}/rest/api/latest/projects/{project}/repos/{repository}/pull-requests/{mypr["id"]}/approve'
            response, info = fetch_url(method="POST", module=module, url=url,
                                       headers=headers, data=json.dumps(data))

            if info['status'] == 401:
                module.fail_json(
                    msg=f"Access denied for user {username}, verify username\
                        and password")
            if info['status'] == 403:
                module.fail_json(msg=f"Access denied for user {username}")

            if info['status'] == [200, 201]:
                result['changed'] = True
            else:
                error_data = json.loads(to_text(response.read()))
                module.fail_json(
                    msg=f"Error approving pull request: {error_data['errors'][0]['message']}")
        except Exception as e:
            module.fail_json(msg=f"Approve PR error: {e}")

    if "merge" in actions:
        try:
            # Get a list of pull requests matching the specified parameters
            prs = getPullRequests(module, result, server, username, password, project,
                                  repository, title)
            mypr = {}

            # Iterate over the retrieved pull requests
            for pr in prs['values']:
                # Check if the pull request is open, has the specified title,
                # and matches the source and destination branches
                if (pr['state'] == 'OPEN' and pr['title'] == title and
                    pr['fromRef']['displayId'] == branch_from and
                        pr['toRef']['displayId'] == branch_to):
                    mypr = pr
                    break

            if mypr == {}:
                module.fail_json(
                    msg=f"Unable to find a PR that matches requested \
                        parameters (title={title})")
            
            mergePullRequest(module, result, server, username, password, 
                             project, repository, mypr["id"], mypr["version"])
        except Exception as e:
            module.fail_json(msg=f"Merge PR error: {e}")

    module.exit_json(**result)


if __name__ == "__main__":
    main()
