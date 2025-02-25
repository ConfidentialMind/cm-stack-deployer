import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from cm_deployer.templates import get_template_path

logger = logging.getLogger(__name__)

class RepoSecretManager:
    """Class for managing repository secrets for ArgoCD."""
    
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize with optional kubeconfig path."""
        # Start with current environment
        self.env = os.environ.copy()
        
        # Add kubeconfig if provided
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"RepoSecretManager using kubeconfig: {kubeconfig}")
            
        # Find kubectl path
        self.kubectl_path = self._find_kubectl()
        if not self.kubectl_path:
            logger.warning("kubectl command not found in PATH or common locations")
    
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
    
    def create_repo_secret(self, secret_name: str, repo_url: str, ssh_key_path: Path) -> bool:
        """Create repository secret from template.
        
        Args:
            secret_name: Name of the secret to create
            repo_url: Git repository URL (SSH format)
            ssh_key_path: Path to SSH private key file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        if not ssh_key_path.exists():
            logger.error(f"SSH key file not found: {ssh_key_path}")
            return False
            
        try:
            # Get template path
            template_path = get_template_path("argocd_repo_secret.yaml")
            
            # Read template and SSH key
            template_content = template_path.read_text()
            ssh_key_content = ssh_key_path.read_text()
            
            # Prepare indented SSH key for YAML
            ssh_lines = ssh_key_content.strip().split('\n')
            indented_ssh_key = '\n    '.join(ssh_lines)
            
            # Fill in template variables
            secret_content = template_content.format(
                secret_name=secret_name,
                repo_url=repo_url,
                ssh_key_indented=f"    {indented_ssh_key}"  # Proper YAML indentation
            )
            
            # Create a temporary file with the secret content
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    temp_file = Path(f.name)
                    f.write(secret_content)
                
                logger.debug(f"Created temporary secret file: {temp_file}")
                
                # Apply the secret
                result = subprocess.run(
                    [self.kubectl_path, "apply", "-f", str(temp_file)],
                    env=self.env,
                    check=True,
                    capture_output=True
                )
                logger.info(f"Applied repository secret '{secret_name}': {result.stdout.decode().strip()}")
                return True
                
            finally:
                # Clean up the temporary file
                if temp_file and temp_file.exists():
                    temp_file.unlink()
                    
        except Exception as e:
            logger.error(f"Error creating repository secret: {str(e)}")
            return False
    
    def delete_repo_secret(self, name: str, namespace: str = "argocd") -> bool:
        """Delete repository secret.
        
        Args:
            name: Name of the secret
            namespace: Namespace where the secret is located
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        try:
            result = subprocess.run(
                [self.kubectl_path, "delete", "secret", name, "-n", namespace],
                env=self.env,
                check=True,
                capture_output=True
            )
            logger.info(f"Deleted repository secret: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete repository secret: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Error deleting repository secret: {str(e)}")
            return False