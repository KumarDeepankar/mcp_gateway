import os
import subprocess
import sys

# --- Configuration ---
# Your Docker Hub username or the name of your remote repository organization.
DOCKER_USERNAME = "deepankar32"

# Define your services here. The script will iterate through this list.
SERVICES = [
    {
        "name": "mcp-server-1",
        "path": "mcp_server_1",
        "dockerfile": "Dockerfile",
        "image_name": f"{DOCKER_USERNAME}/agentic-assistant",
    },
    {
        "name": "tools-gateway",
        "path": "tools_gateway",
        "dockerfile": "mcp_toolbox.dockerfile",
        "image_name": f"{DOCKER_USERNAME}/tools-gateway",
    },
    {
        "name": "ngrok",
        "path": "ngrok",
        "dockerfile": "Dockerfile",
        "image_name": f"{DOCKER_USERNAME}/ngrok-custom",
    },
]


# --- Script Logic ---
def run_command(command, cwd="."):
    """Runs a shell command and streams its output."""
    print(f"Executing: {' '.join(command)}")
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command)
    except FileNotFoundError:
        print(f"\033[91mError: Command '{command[0]}' not found. Is Docker installed and in your PATH?\033[0m")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\033[91mError: Command failed with exit code {e.returncode}.\033[0m")
        sys.exit(1)


def build_and_push(service, tag="latest"):
    """Builds and pushes a Docker image for a given service."""
    name = service["name"]
    path = service["path"]
    dockerfile = service["dockerfile"]
    image_name = service["image_name"]
    full_image_name = f"{image_name}:{tag}"

    print(f"\n---\n\033[94mProcessing service: {name}\033[0m")

    # 1. Build the Docker image
    print(f"\n\033[96mStep 1: Building {full_image_name}...\033[0m")
    build_command = [
        "docker", "build",
        "-f", os.path.join(path, dockerfile),
        "-t", full_image_name,
        path  # The last argument is the build context path
    ]
    # Run from the root of the project
    run_command(build_command, cwd=".")
    print(f"\033[92mSuccessfully built {full_image_name}\033[0m")

    # 2. Push the Docker image
    print(f"\n\033[96mStep 2: Pushing {full_image_name}...\033[0m")
    push_command = ["docker", "push", full_image_name]
    run_command(push_command)
    print(f"\033[92mSuccessfully pushed {full_image_name}\033[0m")


if __name__ == "__main__":
    # Optional: You can pass a specific tag as a command-line argument
    # Example: python build_and_push.py v1.0.1
    image_tag = sys.argv[1] if len(sys.argv) > 1 else "latest"

    print("--- Starting Docker Build and Push Process ---")
    print(f"Using tag: \033[1m{image_tag}\033[0m")

    for service_config in SERVICES:
        build_and_push(service_config, image_tag)

    print("\n\033[92m\033[1mAll services have been successfully built and pushed!\033[0m")
    print("You can now refresh your Kubernetes deployments with 'kubectl rollout restart deployment <deployment-name>'")
