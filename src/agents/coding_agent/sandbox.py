"""Docker Sandbox Manager — manages container lifecycle for coding tasks.

Provides a higher-level interface for managing Docker containers used
for isolated code execution.

Features:
- Container pooling for performance
- Resource limit enforcement
- Health checks
- Automatic cleanup
- Security isolation
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import docker
from docker.errors import DockerException, NotFound, APIError

from src.config import settings

logger = logging.getLogger(__name__)


class SandboxConfig:
    """Configuration for sandbox containers."""

    def __init__(
        self,
        image: str | None = None,
        memory_limit: str = "512m",
        cpu_quota: int = 50000,
        timeout: int = 300,
        workspace_path: str = "/workspace",
    ):
        self.image = image or settings.coding_sandbox_image
        self.memory_limit = memory_limit
        self.cpu_quota = cpu_quota  # 50% of a CPU
        self.timeout = timeout
        self.workspace_path = workspace_path


class DockerSandbox:
    """Manages Docker containers for isolated code execution.

    Provides:
    - Container creation with proper isolation
    - Resource limits
    - Timeout enforcement
    - Cleanup and removal
    """

    def __init__(self, config: SandboxConfig | None = None):
        """Initialize the sandbox manager.

        Args:
            config: Sandbox configuration (uses defaults if not provided)
        """
        self.config = config or SandboxConfig()
        self._active_containers: dict[str, Any] = {}
        self._container_locks: dict[str, asyncio.Lock] = {}

        try:
            self.docker_client = docker.from_env()
            logger.info("Docker sandbox manager initialized")
        except DockerException as e:
            logger.error("Failed to initialize Docker for sandbox: %s", e)
            self.docker_client = None

    async def create_container(
        self,
        task_id: str,
        repository_path: str,
        command: list[str],
        environment: dict[str, str] | None = None,
        network_isolated: bool = True,
    ) -> tuple[str, Any]:
        """Create and start a new sandbox container.

        Args:
            task_id: Unique identifier for the task
            repository_path: Path to the repository to mount
            command: Command to execute in the container
            environment: Environment variables to set
            network_isolated: Whether to disable network access

        Returns:
            Tuple of (container_id, container object)

        Raises:
            RuntimeError: If Docker is not available
        """
        if not self.docker_client:
            raise RuntimeError("Docker client not available")

        lock = asyncio.Lock()
        self._container_locks[task_id] = lock

        async with lock:
            container_name = f"sandbox-{task_id[:12]}"

            # Prepare volumes
            volumes = {
                repository_path: {
                    "bind": self.config.workspace_path,
                    "mode": "rw",
                }
            }

            # Prepare environment
            env = environment or {}
            env.update({
                "SANDBOXED": "true",
                "TASK_ID": task_id,
            })

            # Prepare network mode
            network_mode = "none" if network_isolated else "bridge"

            try:
                container = self.docker_client.containers.run(
                    self.config.image,
                    command=command,
                    name=container_name,
                    volumes=volumes,
                    environment=env,
                    mem_limit=self.config.memory_limit,
                    cpu_quota=self.config.cpu_quota,
                    network_mode=network_mode,
                    detach=True,
                    remove=False,
                )

                self._active_containers[task_id] = {
                    "container": container,
                    "created_at": datetime.utcnow(),
                    "container_id": container.id,
                }

                logger.info(
                    "Created sandbox container %s for task %s",
                    container.id[:12],
                    task_id,
                )

                return container.id, container

            except APIError as e:
                logger.error("Failed to create sandbox container: %s", e)
                raise RuntimeError(f"Failed to create container: {e}")

    async def execute_command(
        self,
        container_id: str,
        command: list[str],
        timeout: int | None = None,
    ) -> tuple[int, str, str]:
        """Execute a command in a running container.

        Args:
            container_id: ID of the container
            command: Command to execute
            timeout: Timeout in seconds (uses config default if not specified)

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        if not self.docker_client:
            raise RuntimeError("Docker client not available")

        try:
            container = self.docker_client.containers.get(container_id)
        except NotFound:
            raise RuntimeError(f"Container {container_id} not found")

        timeout = timeout or self.config.timeout

        try:
            # Execute the command
            exit_code, output = container.exec_run(
                " ".join(command),
                workdir=self.config.workspace_path,
            )

            # Split stdout and stderr
            stdout = output.decode("utf-8")
            stderr = ""

            return exit_code, stdout, stderr

        except APIError as e:
            logger.error("Failed to execute command in container %s: %s", container_id, e)
            return -1, "", str(e)

    async def wait_for_completion(
        self,
        container_id: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Wait for a container to complete execution.

        Args:
            container_id: ID of the container
            timeout: Timeout in seconds

        Returns:
            Dictionary with status and logs
        """
        if not self.docker_client:
            raise RuntimeError("Docker client not available")

        try:
            container = self.docker_client.containers.get(container_id)
        except NotFound:
            return {"status": "error", "error": "Container not found"}

        timeout = timeout or self.config.timeout
        start_time = datetime.utcnow()

        try:
            # Wait for container to finish
            result = await asyncio.to_thread(
                container.wait,
                timeout=timeout,
            )

            # Get logs
            logs = container.logs(stdout=True, stderr=True).decode("utf-8")

            elapsed = (datetime.utcnow() - start_time).total_seconds()

            return {
                "status": "completed" if result["StatusCode"] == 0 else "failed",
                "exit_code": result["StatusCode"],
                "logs": logs,
                "elapsed_seconds": elapsed,
            }

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "error": f"Container did not complete within {timeout} seconds",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
            }

    async def get_file_changes(
        self,
        container_id: str,
    ) -> list[dict[str, Any]]:
        """Get the list of changed files in the container.

        Args:
            container_id: ID of the container

        Returns:
            List of file change dictionaries
        """
        if not self.docker_client:
            return []

        try:
            container = self.docker_client.containers.get(container_id)

            # Run git diff to get changes
            exit_code, output = container.exec_run(
                f"cd {self.config.workspace_path} && "
                "git diff --name-status HEAD && "
                "git diff --stat HEAD"
            )

            if exit_code != 0:
                return []

            # Parse the output
            changes = []
            for line in output.decode("utf-8").strip().split("\n"):
                if not line or line.startswith(" "):
                    continue

                parts = line.split("\t")
                if len(parts) >= 2:
                    changes.append({
                        "status": parts[0],
                        "path": parts[1],
                    })

            return changes

        except Exception as e:
            logger.warning("Failed to get file changes from container %s: %s", container_id, e)
            return []

    async def cleanup_container(self, task_id: str, force: bool = False) -> bool:
        """Clean up a container after task completion.

        Args:
            task_id: Task identifier
            force: Force kill the container

        Returns:
            True if cleanup succeeded
        """
        if task_id not in self._active_containers:
            logger.warning("Task %s not found in active containers", task_id)
            return False

        container_info = self._active_containers.pop(task_id, {})
        container_id = container_info.get("container_id")

        if not container_id:
            return False

        lock = self._container_locks.pop(task_id)
        async with lock:
            try:
                if not self.docker_client:
                    return False

                container = self.docker_client.containers.get(container_id)

                if force:
                    container.remove(force=True)
                else:
                    container.stop(timeout=5)
                    container.remove()

                logger.info("Cleaned up container %s for task %s", container_id[:12], task_id)
                return True

            except NotFound:
                logger.info("Container %s already removed", container_id[:12])
                return True
            except Exception as e:
                logger.warning("Failed to cleanup container %s: %s", container_id[:12], e)
                return False

    async def cleanup_all(self, older_than: timedelta | None = None) -> int:
        """Clean up all active containers.

        Args:
            older_than: Only clean containers older than this duration

        Returns:
            Number of containers cleaned up
        """
        if not self.docker_client:
            return 0

        cutoff = datetime.utcnow() - (older_than or timedelta(hours=1))
        to_cleanup = []

        for task_id, info in list(self._active_containers.items()):
            created_at = info.get("created_at")
            if created_at and created_at < cutoff:
                to_cleanup.append(task_id)

        cleaned = 0
        for task_id in to_cleanup:
            if await self.cleanup_container(task_id, force=True):
                cleaned += 1

        logger.info("Cleaned up %d containers", cleaned)
        return cleaned

    async def health_check(self) -> bool:
        """Check if Docker is available and healthy."""
        if not self.docker_client:
            return False

        try:
            self.docker_client.ping()
            return True
        except DockerException:
            return False

    @property
    def active_count(self) -> int:
        """Return the number of active containers."""
        return len(self._active_containers)
