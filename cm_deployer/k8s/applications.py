import logging
import subprocess
import yaml
import tempfile
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

logger = logging.getLogger(__name__)

class ArgoCDApplication:
    """Class for creating and managing ArgoCD Applications."""
    
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize with optional kubeconfig path."""
        # Start with current environment
        self.env = os.environ.copy()
        
        # Add kubeconfig if provided
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"ArgoCDApplication using kubeconfig: {kubeconfig}")
            
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
    
    def apply_manifest(self, manifest: Dict[str, Any]) -> bool:
        """Apply a Kubernetes manifest using kubectl."""
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        manifest_yaml = yaml.dump(manifest)
        temp_file = None
        try:
            # Create a temporary file for the manifest
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                temp_file = Path(f.name)
                f.write(manifest_yaml)
            
            logger.debug(f"Created temporary manifest file: {temp_file}")
            logger.debug(f"Environment variables: KUBECONFIG={self.env.get('KUBECONFIG', 'not set')}")
            
            # Apply the manifest
            result = subprocess.run(
                [self.kubectl_path, "apply", "-f", str(temp_file)],
                env=self.env,
                check=True,
                capture_output=True
            )
            logger.info(f"Applied manifest: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to apply manifest: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Error applying manifest: {str(e)}")
            return False
        finally:
            # Clean up the temporary file
            if temp_file and temp_file.exists():
                temp_file.unlink()
    
    def create_dependencies_app(self, values: Dict[str, Any], target_revision: str = "HEAD") -> bool:
        """Create or update the Dependencies application.
        
        Args:
            values: Dictionary of values to pass to the Helm chart
            target_revision: Git revision to target (branch, tag, commit SHA, or HEAD)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Creating/updating Dependencies application targeting revision: {target_revision}")
        
        # Format values as YAML string for the manifest
        values_yaml = yaml.dump(values)
        
        manifest = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": "cm-stack-dependencies-root-app",
                "namespace": "argocd"
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": "git@github.com:ConfidentialMind/stack-dependencies.git",
                    "targetRevision": target_revision,
                    "path": "apps",
                    "helm": {
                        "values": values_yaml
                    }
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default"
                },
                "syncPolicy": {
                    "automated": {
                        "selfHeal": True,
                        "prune": True
                    }
                }
            }
        }
        
        logger.debug(f"Dependencies application manifest: {manifest}")
        return self.apply_manifest(manifest)
    
    def create_base_app(self, values: Dict[str, Any], target_revision: str = "HEAD") -> bool:
        """Create or update the Base application.
        
        Args:
            values: Dictionary of values to pass to the Helm chart
            target_revision: Git revision to target (branch, tag, commit SHA, or HEAD)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Creating/updating Base application targeting revision: {target_revision}")
        
        # Format values as YAML string for the manifest
        values_yaml = yaml.dump(values)
        
        manifest = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Application",
            "metadata": {
                "name": "cm-stack-base",
                "namespace": "argocd"
            },
            "spec": {
                "project": "default",
                "source": {
                    "repoURL": "git@github.com:ConfidentialMind/stack-base.git",
                    "targetRevision": target_revision,
                    "path": "helm",
                    "helm": {
                        "values": values_yaml
                    }
                },
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default"
                },
                "syncPolicy": {
                    "automated": {
                        "prune": True,
                        "selfHeal": True
                    },
                    "syncOptions": [
                        "CreateNamespace=true"
                    ]
                }
            }
        }
        
        logger.debug(f"Base application manifest: {manifest}")
        return self.apply_manifest(manifest)
    
    def delete_application(self, name: str, namespace: str = "argocd") -> bool:
        """Delete an ArgoCD Application.
        
        Args:
            name: Name of the application
            namespace: Namespace where the application is located
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        logger.info(f"Deleting application {name} from namespace {namespace}")
        
        try:
            result = subprocess.run(
                [self.kubectl_path, "delete", "application", name, "-n", namespace],
                env=self.env,
                check=True,
                capture_output=True
            )
            logger.info(f"Deleted application: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete application: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Error deleting application: {str(e)}")
            return False