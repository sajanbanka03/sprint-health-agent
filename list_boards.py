"""
List all Jira boards for a project
Helper script for finding board IDs

Author: Sajan Banka
"""
from src.jira_client import JiraClient
from src.utils import load_config

def main():
    config = load_config()
    jira = JiraClient(config)

    # Get project key from config
    project_key = config.get('jira', {}).get('project_key', 'RESMYB')

    print(f"\n📋 Boards for project: {project_key}\n")
    print("-" * 60)

    boards = jira.get_boards_for_project(project_key)

    if not boards:
        print("  No boards found or unable to access project.")
        return

    for board in boards:
        print(f"  📌 {board['name']}")
        print(f"     Board ID: {board['id']}")
        print(f"     Type: {board.get('type', 'unknown')}")
        print()

    print("-" * 60)
    print(f"✅ Total: {len(boards)} boards found\n")

    print("💡 Use these Board IDs in your config.json under 'teams' section:")
    print('   {"name": "Team Name", "board_id": <ID>}')

if __name__ == '__main__':
    main()

