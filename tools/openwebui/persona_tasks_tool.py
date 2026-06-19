"""
title: Persona Task Board
author: project_persona
version: 0.1.0
license: see repo LICENSE
description: Surface the persona's Task Board inside OpenWebUI. Lets the model list the
    current tasks/jobs and inspect one by id, by calling the persona API /tasks endpoint.
requirements: requests

INSTALL (OpenWebUI 0.8.x):
  Admin Panel -> Workspace -> Tools -> "+" -> paste this file -> Save. Then enable the
  tool for a model (or per-chat via the "+" tools menu). The model can then call
  `list_tasks` / `get_task` when the user asks what is being worked on.

CONNECTION:
  Default base URL is http://127.0.0.1:8000 (OpenWebUI run natively, same host as the API,
  e.g. scripts/start_webui.sh). If OpenWebUI runs in Docker, set the `api_base_url` valve to
  http://host.docker.internal:8000. The endpoint is the persona API's GET /tasks (see
  services/api/server.py); this is the SAME data the in-chat persona injection and the
  manage.py status panel use.
"""
from typing import Optional

import requests
from pydantic import BaseModel, Field


def _fmt_task(t: dict) -> str:
    status = t.get("status") or "?"
    title = t.get("title") or t.get("job_id") or "(task)"
    who = f", assignee {t['assignee']}" if t.get("assignee") else ""
    return f"- [{status}] {title} (id {t.get('job_id')}{who})"


class Tools:
    class Valves(BaseModel):
        api_base_url: str = Field(
            default="http://127.0.0.1:8000",
            description="Persona API base URL (use http://host.docker.internal:8000 from Docker).",
        )
        max_tasks: int = Field(default=20, description="Max tasks to list.")
        timeout_s: int = Field(default=10, description="HTTP timeout in seconds.")

    def __init__(self):
        self.valves = self.Valves()

    def list_tasks(self) -> str:
        """List the current tasks/jobs on the persona Task Board (status + title), newest
        first. Use when the user asks what you are working on, what is pending/running, or
        about the task board."""
        url = f"{self.valves.api_base_url.rstrip('/')}/tasks"
        try:
            r = requests.get(url, params={"limit": self.valves.max_tasks}, timeout=self.valves.timeout_s)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            return f"Could not reach the persona task board at {url}: {e}"
        tasks = data.get("tasks") or []
        if not tasks:
            return "The task board is empty right now (0 tasks)."
        head = f"Task board ({data.get('count', len(tasks))} total, showing {len(tasks)}):"
        return head + "\n" + "\n".join(_fmt_task(t) for t in tasks)

    def get_task(self, job_id: str) -> str:
        """Get the full details/state of a single task by its job_id. Use after list_tasks
        when the user asks about a specific task."""
        if not (job_id or "").strip():
            return "Provide a job_id (see list_tasks)."
        url = f"{self.valves.api_base_url.rstrip('/')}/jobs/{job_id.strip()}"
        try:
            r = requests.get(url, timeout=self.valves.timeout_s)
            r.raise_for_status()
            data = r.json()
        except Exception as e:  # noqa: BLE001
            return f"Could not fetch task {job_id}: {e}"
        if data.get("status") == "not_found":
            return f"No task found with id {job_id}."
        lines = [f"Task {job_id}:"]
        for k, v in data.items():
            if k.startswith("_") or k == "job_id":
                continue
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
