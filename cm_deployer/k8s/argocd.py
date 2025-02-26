import subprocess
import time
from pathlib import Path
import logging
import os
from typing import Optional, Dict

logger = logging.getLogger(__name__)

class HelmOperations:
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize Helm operations.
        
        Args:
            kubeconfig: Path to kubeconfig file. Uses default if None.
        """
        # Start with current environment
        self.env = os.environ.copy()
        
        # Add kubeconfig if provided
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"Using kubeconfig: {kubeconfig}")

    def add_repo(self, name: str, url: str) -> bool:
        """Add a Helm repository."""
        try:
            subprocess.run(
                ["helm", "repo", "add", name, url],
                env=self.env,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError as e:
            if b"already exists" in e.stderr:
                logger.info(f"Helm repo {name} already exists")
                return True
            logger.error(f"Failed to add Helm repo: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            logger.error("helm command not found. Please ensure Helm is installed and in PATH")
            return False

    def update_repos(self) -> bool:
        """Update all Helm repositories."""
        try:
            subprocess.run(
                ["helm", "repo", "update"],
                env=self.env,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to update Helm repos: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            logger.error("helm command not found. Please ensure Helm is installed and in PATH")
            return False

    def upgrade_install(
        self,
        release: str,
        chart: str,
        version: Optional[str] = None,
        namespace: str = "default",
        create_namespace: bool = False,
        values_file: Optional[Path] = None
    ) -> bool:
        """Install or upgrade a Helm release."""
        cmd = ["helm", "upgrade", "--install", release, chart, "--namespace", namespace]
        
        if version:
            cmd.extend(["--version", version])
        
        if create_namespace:
            cmd.append("--create-namespace")
        
        if values_file:
            cmd.extend(["-f", str(values_file)])

        try:
            subprocess.run(
                cmd,
                env=self.env,
                check=True,
                capture_output=True
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to install/upgrade Helm release: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            logger.error("helm command not found. Please ensure Helm is installed and in PATH")
            return False

class ArgoCDInstaller:
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize ArgoCD installer."""
        self.helm = HelmOperations(kubeconfig)
        # Store kubeconfig and env for other commands
        self.kubeconfig = kubeconfig
        self.env = os.environ.copy()
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"ArgoCDInstaller using kubeconfig: {kubeconfig}")

    def install(self) -> bool:
        """Install ArgoCD with minimal configuration.
        
        Further configuration will be done by the cm-argocd-self-config app
        deployed through the dependencies application.
        
        Returns:
            bool: True if successful, False otherwise
        """
        # Add and update Helm repo
        if not (self.helm.add_repo("argo", "https://argoproj.github.io/argo-helm") and
                self.helm.update_repos()):
            return False

        # Install ArgoCD with default configuration
        # The cm-argocd-self-config app will handle specific configuration
        success = self.helm.upgrade_install(
            release="argocd",
            chart="argo/argo-cd",
            version="7.8.2",
            namespace="argocd",
            create_namespace=True
        )
        
        if success:
            logger.info("ArgoCD installed successfully (basic installation)")
            logger.info("Further configuration will be applied by cm-argocd-self-config")
            
        return success

    def wait_ready(self, timeout_seconds: int = 300) -> bool:
        """Wait for ArgoCD to be ready."""
        cmd = [
            "kubectl", "wait", "--for=condition=available",
            "--timeout", f"{timeout_seconds}s",
            "-n", "argocd", "deployment", "-l", "app.kubernetes.io/name=argocd-server"
        ]

        try:
            subprocess.run(
                cmd,
                env=self.env,  # Use the environment with KUBECONFIG
                check=True,
                capture_output=True
            )
            logger.info("ArgoCD is ready")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"ArgoCD failed to become ready: {e.stderr.decode()}")
            return False
        except FileNotFoundError:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False

    def get_argocd_credentials(self) -> Dict[str, str]:
        """Get ArgoCD initial admin credentials.
        
        Returns:
            dict: A dictionary with 'username' and 'password' keys
        """
        try:
            # Find kubectl in PATH
            kubectl_cmd = self._find_kubectl()
            if not kubectl_cmd:
                logger.error("kubectl command not found in PATH")
                return {
                    "username": "admin",
                    "password": "error-kubectl-not-found"
                }
                
            # Get the ArgoCD admin password secret
            result = subprocess.run(
                [kubectl_cmd, "get", "secret", "argocd-initial-admin-secret", "-n", "argocd", 
                 "-o", "jsonpath='{.data.password}'"],
                env=self.env,  # Use the environment with KUBECONFIG
                check=True,
                capture_output=True
            )
            
            # Decode the base64 password
            encoded_password = result.stdout.decode().strip("'")
            if not encoded_password:
                logger.warning("ArgoCD password is empty")
                return {
                    "username": "admin",
                    "password": "empty-password"
                }
            
            import base64
            password = base64.b64decode(encoded_password).decode()
            
            return {
                "username": "admin",
                "password": password
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get ArgoCD credentials: {e.stderr.decode()}")
            return {
                "username": "admin",
                "password": "unknown - error retrieving password"
            }
        except Exception as e:
            logger.error(f"Error getting ArgoCD credentials: {str(e)}")
            return {
                "username": "admin",
                "password": "unknown - error processing password"
            }
            
    def _find_kubectl(self) -> Optional[str]:
        """Find kubectl in the system PATH."""
        # Common locations to check
        common_paths = [
            "/usr/bin/kubectl",
            "/usr/local/bin/kubectl",
            "/snap/bin/kubectl"
        ]
        
        # Check if kubectl is in PATH
        for path in common_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                logger.debug(f"Found kubectl at: {path}")
                return path
                
        # Try to find kubectl in PATH
        try:
            which_result = subprocess.run(
                ["which", "kubectl"],
                env=self.env,
                check=True,
                capture_output=True
            )
            kubectl_path = which_result.stdout.decode().strip()
            if kubectl_path:
                logger.debug(f"Found kubectl using 'which': {kubectl_path}")
                return kubectl_path
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
            
        return None