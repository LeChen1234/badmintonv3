"""Platform initialization script.

Creates Label Studio projects, imports annotation templates,
and sets up user mappings.
"""

import os
import sys
import argparse
from typing import Optional

import httpx

LS_HOST = os.getenv("LABEL_STUDIO_HOST", "http://localhost:8080")
LS_API_KEY = os.getenv("LABEL_STUDIO_API_KEY", "")
BACKEND_HOST = os.getenv("BACKEND_HOST", "http://localhost:8000")

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "label-studio", "configs")

TEMPLATES = {
    "skeleton": "skeleton_keypoints.xml",
    "action": "action_classification.xml",
    "combined": "combined_template.xml",
}

HEADERS = {
    "Authorization": f"Token {LS_API_KEY}",
    "Content-Type": "application/json",
}

DEFAULT_USERS = [
    {"username": "expert1", "password": "expert123", "role": "expert", "display_name": "标注专家A"},
    {"username": "leader1", "password": "leader123", "role": "leader", "display_name": "标注组长A"},
    {"username": "student1", "password": "student123", "role": "student", "display_name": "学生标注员1"},
    {"username": "student2", "password": "student123", "role": "student", "display_name": "学生标注员2"},
    {"username": "student3", "password": "student123", "role": "student", "display_name": "学生标注员3"},
]


def load_template(template_type: str) -> str:
    filename = TEMPLATES.get(template_type, TEMPLATES["combined"])
    path = os.path.join(TEMPLATE_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def create_ls_project(client: httpx.Client, name: str, template_type: str = "combined") -> dict:
    label_config = load_template(template_type)
    resp = client.post(
        f"{LS_HOST}/api/projects",
        headers=HEADERS,
        json={
            "title": name,
            "description": f"羽毛球标注项目 - {name}",
            "label_config": label_config,
        },
    )
    resp.raise_for_status()
    project = resp.json()
    print(f"  Created LS project: {project['id']} - {name}")
    return project


def create_backend_user(client: httpx.Client, token: str, user_data: dict) -> Optional[dict]:
    resp = client.post(
        f"{BACKEND_HOST}/api/users",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=user_data,
    )
    if resp.status_code == 201:
        u = resp.json()
        print(f"  Created user: {u['username']} ({u['role']})")
        return u
    elif resp.status_code == 409:
        print(f"  User already exists: {user_data['username']}")
        return None
    else:
        print(f"  Failed to create user {user_data['username']}: {resp.text}")
        return None


def login_admin(client: httpx.Client) -> str:
    resp = client.post(
        f"{BACKEND_HOST}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main():
    parser = argparse.ArgumentParser(description="Initialize the annotation platform")
    parser.add_argument("--skip-ls", action="store_true", help="Skip Label Studio project creation")
    parser.add_argument("--skip-users", action="store_true", help="Skip user creation")
    args = parser.parse_args()

    client = httpx.Client(timeout=30)

    if not args.skip_ls:
        print("\n=== Creating Label Studio Projects ===")
        try:
            create_ls_project(client, "羽毛球骨架标注", "skeleton")
            create_ls_project(client, "羽毛球动作分类", "action")
            create_ls_project(client, "羽毛球综合标注", "combined")
        except Exception as e:
            print(f"  LS project creation failed (is Label Studio running?): {e}")

    if not args.skip_users:
        print("\n=== Creating Backend Users ===")
        try:
            token = login_admin(client)
            for user_data in DEFAULT_USERS:
                create_backend_user(client, token, user_data)
        except Exception as e:
            print(f"  User creation failed (is backend running?): {e}")

    print("\n=== Initialization Complete ===")
    client.close()


if __name__ == "__main__":
    main()
