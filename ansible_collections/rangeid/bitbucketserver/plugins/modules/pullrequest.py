from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule
import requests, json


__metaclass__ = type


DOCUMENTATION = """
"""

def getPullRequests(server,project,repository,username,password,title):
  # TODO: page length >= 1000
  url = f'{server}/rest/api/latest/projects/{project}/repos/{repository}/pull-requests?filterText={title}'
  response = requests.get(url, auth=(username, password))

  if response.status_code == 401:
    module.fail_json(msg=f"Access denied for user {username}, verify username and password")
  if response.status_code == 403:
    module.fail_json(msg=f"Access denied for user {username}")

  return json.loads(response.content.decode('utf-8'))


def main():
    argument_spec = dict(
        server=dict(required=True, type="str"),
        project=dict(required=True, type="str"),
        repository=dict(required=True, type="str"),
        username=dict(required=True, type="str"),
        password=dict(required=True, type="str", no_log=True),
        to_branch=dict(default="master", type="str"),
        from_branch=dict(required=True, type="str"),
        title=dict(required=True, type="str"),
        description=dict(required=False, type="str"),
        author=dict(default="Ansible", type="str"),
        actions=dict(required=True, type="list", choices=['create','approve','merge']),
        ignore_existing_on_create=dict(default=False, type="bool"),
    )

    module = AnsibleModule(
      argument_spec=argument_spec,
    #     required_together=[("comment", "add")],
    #     required_one_of=[("add", "pull", "push")]
    )

    server = module.params.get("server")
    project = module.params.get("project")
    repository = module.params.get("repository")
    branch_to = module.params.get("to_branch")
    branch_from = module.params.get("from_branch")
    title = module.params.get("title")
    description = module.params.get("description")
    username = module.params.get("username")
    password = module.params.get("password")
    ignore_existing_on_create = module.params.get("ignore_existing_on_create")
    actions = module.params.get("actions")
    author = module.params.get("author")

    module.run_command_environ_update = dict(
        LANG="C.UTF-8", LC_ALL="C.UTF-8", LC_MESSAGES="C.UTF-8", LC_CTYPE="C.UTF-8"
    )
    result = dict(changed=False)

    if not server.startswith("https://"):
      module.fail_json('Server must be https://<servername>')

    if "create" in actions:
      module.warn(f"Create branch in action")
      new_pr = {
          "title": title,
          "description": description,
          "state": "OPEN",
          "open": True,
          "closed": False,
          "fromRef": {
              "id": branch_from,
              "repository": {
                  "slug": repository,
                  "project": {
                      "key": project,

                  }
              }
          },
          "toRef": {
              "id": branch_to,
              "repository": {
                  "slug": repository,
                  "project": {
                      "key": project,
                  }
              }
          }
      }

      try:
        url = f'{server}/rest/api/latest/projects/{project}/repos/{repository}/pull-requests'
        response = requests.post(url, auth=(username, password), json=new_pr)

        if response.status_code == 401:
          module.fail_json(msg=f"Access denied for user {username}, verify username and password")
        if response.status_code == 403:
          module.fail_json(msg=f"Access denied for user {username}")

        if response.status_code == 409 and ignore_existing_on_create == True:
           module.warn('A pull-request already exists, ignoring error as requested')
        else:
          if response.ok:
            pass
          else:
              error_data = json.loads(response.content.decode('utf-8'))
              module.fail_json(msg=f"Error creating new pull request: {error_data['errors'][0]['message']}")
      except requests.exceptions.RequestException as e:
        module.fail_json(msg=f"Request error: {e}")

    if "approve" in actions:
      module.warn(f"Approve pull-request in action")
      try:
        prs = getPullRequests(server,project,repository,username,password,title)
        mypr = {}
        for pr in prs['values']:
          if pr['state'] == 'OPEN' and pr['title'] == title and pr['fromRef']['displayId'] == branch_from and pr['toRef']['displayId'] == branch_to:
            mypr = pr
            break
        
        if mypr == {}:
           module.fail_json(msg=f"Unable to find a PR that matches requested parameters")
       
        data = {
          "user": {
              "name": author
          },
          "approved": True,
          "status": "APPROVED"
        }

        url = f'{server}/rest/api/latest/projects/{project}/repos/{repository}/pull-requests/{mypr["id"]}/approve'
        response = requests.post(url, auth=(username, password), json=data)

        if response.status_code == 401:
          module.fail_json(msg=f"Access denied for user {username}, verify username and password")
        if response.status_code == 403:
          module.fail_json(msg=f"Access denied for user {username}")


        if response.ok:
          pass
        else:
          print(response.content)
          error_data = json.loads(response.content.decode('utf-8'))
          module.fail_json(msg=f"Error approving pull request: {error_data['errors'][0]['message']}")
      except requests.exceptions.RequestException as e:
        module.fail_json(msg=f"Request error: {e}")

    if "merge" in actions:
      module.warn(f"Merge pull-request in action")


      try:
        prs = getPullRequests(server,project,repository,username,password,title)
        mypr = {}
        for pr in prs['values']:
          if pr['state'] == 'OPEN' and pr['title'] == title and pr['fromRef']['displayId'] == branch_from and pr['toRef']['displayId'] == branch_to:
            mypr = pr
            break
        
        if mypr == {}:
            module.fail_json(msg=f"Unable to find a PR that matches requested parameters")

        data = {
          "version": mypr['version']
        }
        url = f'{server}/rest/api/latest/projects/{project}/repos/{repository}/pull-requests/{mypr["id"]}/merge'
        response = requests.post(url, auth=(username, password), json=data)
        if response.status_code == 401:
          module.fail_json(msg=f"Access denied for user {username}, verify username and password")
        if response.status_code == 403:
          module.fail_json(msg=f"Access denied for user {username}")


        if response.ok:
          pass
        else:
          print(response.content)
          error_data = json.loads(response.content.decode('utf-8'))
          module.fail_json(msg=f"Error approving pull request: {error_data['errors'][0]['message']}")
      except requests.exceptions.RequestException as e:
        module.fail_json(msg=f"Request error: {e}")



    module.exit_json(**result)


if __name__ == "__main__":
  main()