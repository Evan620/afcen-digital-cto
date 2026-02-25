"""Claude Code Docker Executor — runs Claude Code in isolated containers.

This module handles the execution of coding tasks using Claude Code CLI
within Docker containers for safety and isolation.

Key features:
- Isolated execution per task
- Mounts repository as volume
- Captures output and changes
- Timeout protection
- Resource limits
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import docker
from docker.errors import DockerException, ContainerError, APIError

from src.agents.coding_agent.models import (
    CodingAgentType,
    CodingComplexity,
    CodingResult,
    CodingTask,
    FileChange,
    TaskStatus,
    TestResult,
    RepoAccessMode,
)
from src.config import settings

logger = logging.getLogger(__name__)


# ── Claude Code System Prompt ──

CLAUUDE_CODE_SYSTEM_PROMPT = """You are Claude Code, an AI coding assistant.

Your task is to implement the requested changes following these guidelines:

1. **Quality**: Write clean, well-documented code following existing patterns in the repository.
2. **Testing**: If tests are required, write appropriate tests for your changes.
3. **Scope**: Only modify files necessary to complete the task. Do not make extraneous changes.
4. **Security**: Never expose credentials, API keys, or sensitive data.
5. **Compatibility**: Follow the existing code style and conventions.

When complete, provide a summary of:
- Files modified
- Changes made
- Any tests added/modified
- Potential issues or follow-up items

Do NOT modify:
- Configuration files (.env, secrets)
- CI/CD configurations unless explicitly requested
- Database migrations without explicit approval
- Dependencies without justification
"""


# ── Executor Class ──


class ClaudeCodeExecutor:
    """Execute coding tasks using Claude Code in Docker containers.

    Each task runs in an isolated container with:
    - Repository mounted as volume
    - Timeouts enforced
    - Resource limits
    - Output capture
    """

    CONTAINER_IMAGE = os.getenv(
        "CLAUDE_CODE_IMAGE",
        "digital-cto-claude-code:latest",  # Custom Claude Code image
    )
    WORKSPACE_PATH = "/workspace"

    def __init__(
        self,
        repo_path: str | None = None,
        timeout: int = 300,
        anthropic_api_key: str | None = None,
    ):
        """Initialize the executor.

        Args:
            repo_path: Local path to the repository (for testing)
            timeout: Maximum execution time in seconds
            anthropic_api_key: Anthropic API key for Claude Code
        """
        self.timeout = timeout
        self.repo_path = repo_path or settings.coding_workspace_path
        self.anthropic_api_key = anthropic_api_key or settings.anthropic_api_key

        try:
            self.docker_client = docker.from_env()
            logger.info("Docker client initialized for Claude Code executor")
        except DockerException as e:
            logger.error("Failed to initialize Docker client: %s", e)
            self.docker_client = None

    async def execute_task(self, task: CodingTask) -> CodingResult:
        """Execute a coding task in an isolated Docker container.

        Args:
            task: The coding task to execute

        Returns:
            CodingResult with execution outcome
        """
        if not self.docker_client:
            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.FAILED,
                errors=["Docker client not available"],
            )

        started_at = datetime.utcnow()
        container_id = None

        try:
            # 1. Prepare the workspace (returns path and clone_url/strategy)
            workspace_mount, clone_url = await self._prepare_workspace(task)

            # 2. Build the command
            command = self._build_command(task)

            # 3. Create and start container (skip if using gh CLI)
            if clone_url == "gh":
                # Use GitHub CLI mode - no container needed
                return await self._execute_with_gh_cli(task, started_at)

            container = await self._create_container(task, workspace_mount, command)
            container_id = container.id
            logger.info("Started container %s for task %s", container_id[:12], task.task_id)

            # 4. Execute with timeout
            output = await self._run_with_timeout(container)

            # 5. Capture results
            files_modified = await self._get_modified_files(task, container)

            # 6. Clean up
            await self._cleanup_container(container)

            completed_at = datetime.utcnow()
            execution_time = (completed_at - started_at).total_seconds()

            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.EXECUTING,
                files_modified=files_modified,
                execution_time_seconds=execution_time,
                docker_container_id=container_id,
                started_at=started_at,
                completed_at=completed_at,
                errors=[],
            )

        except asyncio.TimeoutError:
            logger.error("Task %s timed out after %d seconds", task.task_id, self.timeout)
            if container_id:
                await self._force_cleanup(container_id)

            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.FAILED,
                errors=[f"Execution timed out after {self.timeout} seconds"],
                execution_time_seconds=self.timeout,
                docker_container_id=container_id,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except (ContainerError, APIError) as e:
            logger.error("Docker error for task %s: %s", task.task_id, e)
            if container_id:
                await self._force_cleanup(container_id)

            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.FAILED,
                errors=[f"Docker error: {str(e)}"],
                execution_time_seconds=(datetime.utcnow() - started_at).total_seconds(),
                docker_container_id=container_id,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

        except Exception as e:
            logger.exception("Unexpected error executing task %s", task.task_id)
            if container_id:
                await self._force_cleanup(container_id)

            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.FAILED,
                errors=[f"Unexpected error: {str(e)}"],
                execution_time_seconds=(datetime.utcnow() - started_at).total_seconds(),
                docker_container_id=container_id,
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def _prepare_workspace(self, task: CodingTask) -> tuple[str, str]:
        """Prepare workspace based on repository access strategy.

        Returns:
            Tuple of (workspace_path, git_clone_url)
        """
        # Determine access strategy
        strategy = task.repo_access_mode or self._select_strategy(task)

        logger.info("Using repo access strategy: %s for task %s", strategy.value, task.task_id)

        if strategy == RepoAccessMode.PERSISTENT_WORKSPACE:
            return await self._use_persistent_workspace(task)

        elif strategy == RepoAccessMode.GITHUB_CLI:
            # gh CLI doesn't need local clone, returns empty workspace
            return "", "gh"

        else:  # CLONE_ON_DEMAND (default)
            return await self._clone_repository(task)

    def _select_strategy(self, task: CodingTask) -> RepoAccessMode:
        """Auto-select repository access strategy based on task characteristics."""
        # Simple tasks with minimal file changes -> gh CLI (fastest)
        if task.complexity in (CodingComplexity.TRIVIAL, CodingComplexity.SIMPLE):
            if task.estimated_files <= 3:
                return RepoAccessMode.GITHUB_CLI

        # Complex tasks requiring full codebase understanding -> persistent workspace
        if task.complexity in (CodingComplexity.COMPLEX, CodingComplexity.VERY_COMPLEX):
            return RepoAccessMode.PERSISTENT_WORKSPACE

        # Default: clone on demand for isolated execution
        return RepoAccessMode.CLONE_ON_DEMAND

    async def _clone_repository(self, task: CodingTask) -> tuple[str, str]:
        """Clone repository for task execution.

        Returns:
            Tuple of (workspace_path, clone_url)
        """
        workspace = os.path.join(self.repo_path, task.task_id)
        os.makedirs(workspace, exist_ok=True)

        # Build clone URL with authentication
        if settings.github_token:
            clone_url = f"https://x-access-token:{settings.github_token}@github.com/{task.repository}.git"
        else:
            clone_url = f"https://github.com/{task.repository}.git"

        # Git clone command
        cmd = [
            "git",
            "clone",
            "--depth", "1",  # Shallow clone for speed
            "--single-branch",
            "--branch", task.base_branch,
            clone_url,
            workspace
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode()
            logger.error("Git clone failed for %s: %s", task.repository, error_msg)
            raise RuntimeError(f"Git clone failed: {error_msg}")

        logger.info("Cloned %s to %s", task.repository, workspace)
        return workspace, clone_url

    async def _use_persistent_workspace(self, task: CodingTask) -> tuple[str, str]:
        """Use pre-cloned persistent workspace.

        Returns:
            Tuple of (workspace_path, repo_identifier)
        """
        workspace = os.path.join(self.repo_path, task.repository.replace("/", "_"))

        # Clone if doesn't exist
        if not os.path.exists(workspace):
            os.makedirs(self.repo_path, exist_ok=True)
            await self._clone_repository(task)

        # Fetch latest changes
        cmd = ["git", "-C", workspace, "fetch", "origin"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

        logger.info("Using persistent workspace: %s", workspace)
        return workspace, f"persistent:{task.repository}"

    def _build_command(self, task: CodingTask) -> list[str]:
        """Build the command to run Claude Code CLI in the container."""
        from src.agents.coding_agent.models import AutonomyLevel

        # Base claude command with non-interactive mode
        command = [
            "claude",
            "--yes",                    # Auto-confirm all prompts
            "--dangerously-skip-safety", # Allow file modifications
            "--suppress-safety",
        ]

        # Add tool restrictions based on task autonomy level
        if task.autonomy_level == AutonomyLevel.SUPERVISED:
            command.extend(["--allowedTools", "read,view"])
        elif task.autonomy_level == AutonomyLevel.SEMI_AUTONOMOUS:
            command.extend(["--allowedTools", "read,view,write,bash,edit"])
        # fully_autonomous = all tools (default)

        # Add the prompt as the primary command
        command.extend(["-p", task.description])

        return command

    async def _execute_with_gh_cli(self, task: CodingTask, started_at: datetime) -> CodingResult:
        """Execute task using GitHub CLI API (no local clone).

        This mode is fastest for simple tasks with minimal file changes.
        Uses gh CLI to create PRs and edit files directly via GitHub API.
        """
        import subprocess

        logger.info("Executing task %s with gh CLI mode", task.task_id)

        try:
            # Create a feature branch name
            branch_name = f"digital-cto-{task.task_id[:12]}"
            base_sha = await self._get_default_branch_sha(task.repository, task.base_branch)

            # Create branch using gh CLI
            create_branch_cmd = [
                "gh", "api",
                "--method", "POST",
                "-f", f"ref=refs/heads/{branch_name}",
                "-f", f"sha={base_sha}",
                f"repos/{task.repository}/git/refs",
            ]

            process = await asyncio.create_subprocess_exec(
                *create_branch_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "GH_TOKEN": settings.github_token},
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0 and "already exists" not in stderr.decode():
                logger.warning("Failed to create branch: %s", stderr.decode())

            # Use GitHub CLI to create a PR with the task description
            # The PR will be created with a placeholder commit that triggers
            # Claude Code execution via a GitHub Action
            pr_title = task.description[:100] + "..." if len(task.description) > 100 else task.description

            create_pr_cmd = [
                "gh", "pr", "create",
                "--repo", task.repository,
                "--base", task.base_branch,
                "--head", branch_name,
                "--title", pr_title,
                "--body", f"Digital CTO Task: {task.description}\n\nTask ID: {task.task_id}",
                "--draft",  # Create as draft initially
            ]

            process = await asyncio.create_subprocess_exec(
                *create_pr_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "GH_TOKEN": settings.github_token},
            )
            stdout, stderr = await process.communicate()

            completed_at = datetime.utcnow()
            execution_time = (completed_at - started_at).total_seconds()

            if process.returncode == 0:
                # Extract PR number from output
                output = stdout.decode()
                logger.info("Created draft PR via gh CLI: %s", output[:200])

                return CodingResult(
                    task_id=task.task_id,
                    agent_used=CodingAgentType.CLAUDE_CODE,
                    status=TaskStatus.EXECUTING,
                    execution_time_seconds=execution_time,
                    started_at=started_at,
                    completed_at=completed_at,
                    errors=[],
                )
            else:
                error_msg = stderr.decode()
                logger.error("Failed to create PR via gh CLI: %s", error_msg)
                return CodingResult(
                    task_id=task.task_id,
                    agent_used=CodingAgentType.CLAUDE_CODE,
                    status=TaskStatus.FAILED,
                    errors=[f"gh CLI failed: {error_msg}"],
                    execution_time_seconds=execution_time,
                    started_at=started_at,
                    completed_at=completed_at,
                )

        except Exception as e:
            logger.exception("gh CLI execution failed")
            return CodingResult(
                task_id=task.task_id,
                agent_used=CodingAgentType.CLAUDE_CODE,
                status=TaskStatus.FAILED,
                errors=[f"gh CLI mode failed: {str(e)}"],
                execution_time_seconds=(datetime.utcnow() - started_at).total_seconds(),
                started_at=started_at,
                completed_at=datetime.utcnow(),
            )

    async def _get_default_branch_sha(self, repository: str, branch: str) -> str:
        """Get the SHA of the default branch tip."""
        import subprocess

        cmd = [
            "gh", "api",
            f"repos/{repository}/git/refs/heads/{branch}",
            "--jq", ".object.sha",
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "GH_TOKEN": settings.github_token},
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return stdout.decode().strip()
        else:
            # Fallback: try to get default branch
            cmd = ["gh", "repo", "view", repository, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.target.oid"]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "GH_TOKEN": settings.github_token},
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.warning("Failed to get branch SHA, using empty sha")
                return ""

    async def _create_container(
        self,
        task: CodingTask,
        workspace_mount: str,
        command: list[str],
    ) -> Any:
        """Create and start a Docker container for the task."""
        container_name = f"coding-task-{task.task_id[:12]}"

        environment = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "GITHUB_TOKEN": settings.github_token or "",
            "TASK_ID": task.task_id,
            "TASK_DESCRIPTION": task.description,
            "CLAUDE_DEFAULT_MODEL": os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
        }

        # Set up volumes
        volumes = {}
        if workspace_mount:
            volumes[workspace_mount] = {"bind": self.WORKSPACE_PATH, "mode": "rw"}

        # Add git config volume for persistent credentials
        git_config_volume = os.getenv("GIT_CONFIG_VOLUME", "/tmp/git_config")
        if os.path.exists(git_config_volume):
            volumes[git_config_volume] = {"bind": "/root/.git", "mode": "ro"}

        mem_limit = "512m"
        cpu_quota = 50000  # 50% of a CPU

        container = self.docker_client.containers.run(
            self.CONTAINER_IMAGE,
            command=command,
            name=container_name,
            volumes=volumes or None,  # None if empty dict
            environment=environment,
            mem_limit=mem_limit,
            cpu_quota=cpu_quota,
            detach=True,
            remove=False,
            network_mode="host",  # Use host network for API access
        )

        return container

    async def _run_with_timeout(self, container: Any) -> str:
        """Run the container and wait for completion with timeout."""
        loop = asyncio.get_event_loop()

        async def wait_for_container():
            return await loop.run_in_executor(
                None,
                lambda: container.wait(timeout=self.timeout),
            )

        await asyncio.wait_for(wait_for_container(), timeout=self.timeout)

        # Get logs
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")
        return logs

    async def _get_modified_files(self, task: CodingTask, container: Any) -> list[FileChange]:
        """Get the list of modified files from the container."""
        try:
            # Run git diff --name-status to get changes
            exit_code, output = container.exec_run(
                f"cd {self.WORKSPACE_PATH} && git diff --name-status HEAD",
            )

            if exit_code != 0:
                return []

            files: list[FileChange] = []
            for line in output.decode("utf-8").strip().split("\n"):
                if not line:
                    continue

                parts = line.split("\t")
                if len(parts) >= 2:
                    status, path = parts[0], parts[1]
                    files.append(FileChange(path=path, status=status))

            return files

        except Exception as e:
            logger.warning("Failed to get modified files: %s", e)
            return []

    async def _cleanup_container(self, container: Any):
        """Clean up a container after execution."""
        try:
            container.stop(timeout=5)
            container.remove()
        except Exception as e:
            logger.warning("Failed to cleanup container: %s", e)

    async def _force_cleanup(self, container_id: str):
        """Force cleanup of a container by ID."""
        try:
            container = self.docker_client.containers.get(container_id)
            container.stop(timeout=1)
            container.remove(force=True)
        except Exception as e:
            logger.warning("Failed to force cleanup container %s: %s", container_id, e)


# ── Mock Executor for Testing ──


class MockCodeExecutor(ClaudeCodeExecutor):
    """Mock executor for testing without Docker.

    Simulates code generation without actually running containers.
    """

    async def execute_task(self, task: CodingTask) -> CodingResult:
        """Simulate task execution."""
        started_at = datetime.utcnow()

        # Simulate processing time
        await asyncio.sleep(0.5)

        # Generate mock results
        files_modified = []
        if "endpoint" in task.description.lower():
            files_modified.append(
                FileChange(
                    path="src/api/endpoints.py",
                    status="modified",
                    additions=15,
                    deletions=2,
                )
            )

        completed_at = datetime.utcnow()
        execution_time = (completed_at - started_at).total_seconds()

        return CodingResult(
            task_id=task.task_id,
            agent_used=CodingAgentType.CLAUDE_CODE,
            status=TaskStatus.EXECUTING,
            files_modified=files_modified,
            execution_time_seconds=execution_time,
            started_at=started_at,
            completed_at=completed_at,
        )
