import os
import sys
import json
import re
import urllib.request
from pathlib import Path

PROJECTS = {
    "Workspace & Dev Productivity": {
        "number": 5,
        "id": "PVT_kwHOCh2ip84Bk9qX",
        "url": "https://github.com/users/matheus-condotta/projects/5",
        "status_field_id": "PVTSSF_lAHOCh2ip84Bk9qXzhjsR0o",
        "status_options": {
            "Backlog": "6b1b874a",
            "Ready": "0421065f",
            "In progress": "9bfd6e75",
            "In review": "8d2dc4ea",
            "Done": "bab89fe8"
        },
        "repos": ["antigravity-project", "antigravity-voice", "antigravity-meeting"]
    },
    "Data Platforms & Analytics": {
        "number": 6,
        "id": "PVT_kwHOCh2ip84BlAGw",
        "url": "https://github.com/users/matheus-condotta/projects/6",
        "status_field_id": "PVTSSF_lAHOCh2ip84BlAGwzhjul4A",
        "status_options": {
            "Backlog": "5d221129",
            "Ready": "261bae76",
            "In progress": "3d6e86c6",
            "In review": "117527fe",
            "Done": "442307cd"
        },
        "repos": ["pipeline-pyspark-dbt-airflow", "consilio"]
    },
    "Operations & Utilities": {
        "number": 7,
        "id": "PVT_kwHOCh2ip84BlAHF",
        "url": "https://github.com/users/matheus-condotta/projects/7",
        "status_field_id": "PVTSSF_lAHOCh2ip84BlAHFzhjumLc",
        "status_options": {
            "Backlog": "d9f03d8e",
            "Ready": "7351b31d",
            "In progress": "e887e88e",
            "In review": "abc6811a",
            "Done": "b6d505bd"
        },
        "repos": ["documenso", "documenso-private", "cdt-hub", "signature_generator", "erpnext", "erpnext-private"]
    },
    "Knowledge & Gaming": {
        "number": 8,
        "id": "PVT_kwHOCh2ip84BlAHH",
        "url": "https://github.com/users/matheus-condotta/projects/8",
        "status_field_id": "PVTSSF_lAHOCh2ip84BlAHHzhjumNM",
        "status_options": {
            "Backlog": "d3552df6",
            "Ready": "0374a38a",
            "In progress": "9cf2ac35",
            "In review": "37b83c63",
            "Done": "da61a3c7"
        },
        "repos": ["aion2-guide"]
    }
}


def get_project_for_repo(repo_name: str) -> dict:
    repo_clean = repo_name.split("/")[-1].lower()
    for p_name, p_data in PROJECTS.items():
        if any(r.lower() == repo_clean for r in p_data["repos"]):
            return p_data
    return PROJECTS["Workspace & Dev Productivity"]


def execute_graphql(query: str, variables: dict = None, token: str = "") -> dict:
    if not token:
        raise RuntimeError("Token do GitHub nao fornecido.")

    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "AntigravityProjectAction/1.0",
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        if "errors" in data:
            raise RuntimeError(f"Erro na API GraphQL: {data['errors']}")
        return data.get("data", {})


def get_issue_node_id(owner: str, name: str, issue_number: int, token: str) -> str:
    query = """
    query($owner: String!, $name: String!, $number: Int!) {
      repository(owner: $owner, name: $name) {
        issue(number: $number) {
          id
        }
      }
    }
    """
    data = execute_graphql(query, {"owner": owner, "name": name, "number": issue_number}, token=token)
    issue = data.get("repository", {}).get("issue")
    if not issue:
        raise ValueError(f"Issue #{issue_number} nao encontrada em {owner}/{name}")
    return issue["id"]


def add_issue_to_project(content_id: str, project_id: str, token: str) -> str:
    mutation = """
    mutation($projectId: ID!, $contentId: ID!) {
      addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
          id
        }
      }
    }
    """
    data = execute_graphql(mutation, {"projectId": project_id, "contentId": content_id}, token=token)
    return data["addProjectV2ItemById"]["item"]["id"]


def find_project_item_id(owner: str, project_number: int, repo_name: str, issue_number: int, token: str) -> str:
    repo_clean = repo_name.split("/")[-1].lower()
    query = f"""
    query {{
      user(login: "{owner}") {{
        projectV2(number: {project_number}) {{
          items(first: 100) {{
            nodes {{
              id
              content {{
                ... on Issue {{
                  number
                  repository {{
                    name
                    nameWithOwner
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
    """
    data = execute_graphql(query, token=token)
    items = data.get("user", {}).get("projectV2", {}).get("items", {}).get("nodes", [])
    for node in items:
        cnt = node.get("content")
        if not cnt:
            continue
        num = cnt.get("number")
        r_obj = cnt.get("repository", {})
        r_name = r_obj.get("name", "").lower()
        r_full = r_obj.get("nameWithOwner", "").lower()
        if num == issue_number and (repo_clean in (r_name, r_full)):
            return node["id"]
    return ""


def set_status_by_item_id(item_id: str, status_name: str, project_id: str, field_id: str, status_options: dict, token: str) -> bool:
    if status_name not in status_options:
        raise ValueError(f"Status invalido '{status_name}'. Opcoes: {list(status_options.keys())}")

    option_id = status_options[status_name]
    mutation = """
    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
      updateProjectV2ItemFieldValue(
        input: {
          projectId: $projectId
          itemId: $itemId
          fieldId: $fieldId
          value: { singleSelectOptionId: $optionId }
        }
      ) {
        projectV2Item {
          id
        }
      }
    }
    """
    vars_ = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "optionId": option_id
    }
    execute_graphql(mutation, vars_, token=token)
    return True


def archive_project_item(item_id: str, project_id: str, token: str) -> bool:
    mutation = """
    mutation($projectId: ID!, $itemId: ID!) {
      archiveProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
        projectV2Item {
          id
        }
      }
    }
    """
    execute_graphql(mutation, {"projectId": project_id, "itemId": item_id}, token=token)
    return True


def sync_issue_status(owner: str, repo: str, issue_number: int, status_name: str, token: str) -> str:
    proj_cfg = get_project_for_repo(repo)
    item_id = find_project_item_id(owner, proj_cfg["number"], repo, issue_number, token)
    if not item_id:
        content_id = get_issue_node_id(owner, repo, issue_number, token)
        item_id = add_issue_to_project(content_id, proj_cfg["id"], token)

    set_status_by_item_id(
        item_id=item_id,
        status_name=status_name,
        project_id=proj_cfg["id"],
        field_id=proj_cfg["status_field_id"],
        status_options=proj_cfg["status_options"],
        token=token
    )
    return item_id


def extract_linked_issues(body: str, branch_name: str = "") -> list[int]:
    issues = set()
    if body:
        matches = re.findall(r"(?i)(?:close|closes|closed|fix|fixes|fixed|resolve|resolves|resolved)\s+#(\d+)", body)
        for m in matches:
            issues.add(int(m))

    if branch_name:
        b_match = re.search(r"(?:feat|fix|chore)/issue-(\d+)", branch_name)
        if b_match:
            issues.add(int(b_match.group(1)))

    return sorted(list(issues))


def handle_event(event_name: str, payload: dict, token: str) -> list[str]:
    logs = []
    repository = payload.get("repository", {})
    owner = repository.get("owner", {}).get("login", "matheus-condotta")
    repo_name = repository.get("name", "")

    if event_name == "issues":
        action = payload.get("action")
        issue = payload.get("issue", {})
        issue_number = issue.get("number")
        if not issue_number:
            return ["Nenhuma issue identificada no payload."]

        if action in ("opened", "reopened"):
            sync_issue_status(owner, repo_name, issue_number, "Backlog", token)
            logs.append(f"Issue #{issue_number} adicionada ao board em 'Backlog'.")
        elif action == "labeled":
            label_name = payload.get("label", {}).get("name", "").strip().lower()
            if label_name in ("ready", "status: ready", "status:ready"):
                sync_issue_status(owner, repo_name, issue_number, "Ready", token)
                logs.append(f"Issue #{issue_number} transicionada para 'Ready'.")
            elif label_name in ("in progress", "in-progress", "status: in-progress", "status:in-progress"):
                sync_issue_status(owner, repo_name, issue_number, "In progress", token)
                logs.append(f"Issue #{issue_number} transicionada para 'In progress'.")
        elif action == "closed":
            state_reason = issue.get("state_reason")
            sync_issue_status(owner, repo_name, issue_number, "Done", token)
            logs.append(f"Issue #{issue_number} transicionada para 'Done'.")
            if state_reason == "not_planned":
                proj_cfg = get_project_for_repo(repo_name)
                item_id = find_project_item_id(owner, proj_cfg["number"], repo_name, issue_number, token)
                if item_id:
                    archive_project_item(item_id, proj_cfg["id"], token)
                    logs.append(f"Issue #{issue_number} arquivada por encerramento como not planned.")

    elif event_name == "pull_request":
        action = payload.get("action")
        pr = payload.get("pull_request", {})
        body = pr.get("body") or ""
        branch = pr.get("head", {}).get("ref") or ""
        is_draft = pr.get("draft", False)
        linked_issues = extract_linked_issues(body, branch)

        if not linked_issues:
            logs.append(f"PR #{pr.get('number')} processado sem issues vinculadas.")
            return logs

        if action in ("opened", "ready_for_review"):
            target_status = "In progress" if is_draft else "In review"
            for num in linked_issues:
                sync_issue_status(owner, repo_name, num, target_status, token)
                logs.append(f"Issue vinculada #{num} transicionada para '{target_status}'.")
        elif action == "converted_to_draft":
            for num in linked_issues:
                sync_issue_status(owner, repo_name, num, "In progress", token)
                logs.append(f"Issue vinculada #{num} transicionada para 'In progress' (Draft).")
        elif action == "closed":
            if pr.get("merged", False):
                for num in linked_issues:
                    sync_issue_status(owner, repo_name, num, "Done", token)
                    logs.append(f"Issue vinculada #{num} transicionada para 'Done' (PR Mergeado).")

    return logs


def main():
    token = os.environ.get("PROJECTS_PIPELINE_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Erro: Variavel de ambiente PROJECTS_PIPELINE_TOKEN nao configurada.")
        sys.exit(1)

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    event_name = os.environ.get("GITHUB_EVENT_NAME")

    if not event_path or not Path(event_path).exists():
        print("Execucao fora do ambiente de GitHub Actions ou GITHUB_EVENT_PATH inexistente.")
        sys.exit(0)

    with open(event_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    logs = handle_event(event_name, payload, token)
    for line in logs:
        print(line)


if __name__ == "__main__":
    main()
