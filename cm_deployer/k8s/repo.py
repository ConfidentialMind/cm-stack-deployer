import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any, Set

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


class ArgoCDComponentManager:
    """Class for managing ArgoCD components like repo server and application controller."""
    
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize with optional kubeconfig path."""
        # Start with current environment
        self.env = os.environ.copy()
        
        # Add kubeconfig if provided
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"ArgoCDComponentManager using kubeconfig: {kubeconfig}")
            
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
    
    def get_all_argocd_deployments(self) -> List[str]:
        """Get all ArgoCD deployments in the argocd namespace.
        
        Returns:
            List[str]: List of deployment names
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return []
            
        try:
            result = subprocess.run(
                [self.kubectl_path, "get", "deployments", "-n", "argocd", 
                 "-l", "app.kubernetes.io/part-of=argocd", 
                 "-o", "jsonpath='{.items[*].metadata.name}'"],
                env=self.env,
                check=True,
                capture_output=True
            )
            
            deployments = result.stdout.decode().strip("'").split()
            return deployments
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get ArgoCD deployments: {e.stderr.decode()}")
            return []
        except Exception as e:
            logger.warning(f"Error getting ArgoCD deployments: {str(e)}")
            return []
    
    def get_all_argocd_statefulsets(self) -> List[str]:
        """Get all ArgoCD statefulsets in the argocd namespace.
        
        Returns:
            List[str]: List of statefulset names
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return []
            
        try:
            result = subprocess.run(
                [self.kubectl_path, "get", "statefulsets", "-n", "argocd", 
                 "-l", "app.kubernetes.io/part-of=argocd", 
                 "-o", "jsonpath='{.items[*].metadata.name}'"],
                env=self.env,
                check=True,
                capture_output=True
            )
            
            statefulsets = result.stdout.decode().strip("'").split()
            return statefulsets
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to get ArgoCD statefulsets: {e.stderr.decode()}")
            return []
        except Exception as e:
            logger.warning(f"Error getting ArgoCD statefulsets: {str(e)}")
            return []
    
    def wait_for_all_argocd_pods_ready(self, timeout_seconds: int = 300) -> bool:
        """Wait for all ArgoCD pods to be ready.
        
        Args:
            timeout_seconds: Maximum time to wait in seconds
            
        Returns:
            bool: True if all pods are ready, False if timeout
        """
        logger.info("Waiting for all ArgoCD pods to be ready...")
        
        # Get all ArgoCD deployments and statefulsets
        deployments = self.get_all_argocd_deployments()
        statefulsets = self.get_all_argocd_statefulsets()
        
        if not deployments and not statefulsets:
            logger.warning("No ArgoCD deployments or statefulsets found")
            return False
        
        logger.info(f"Found ArgoCD deployments: {', '.join(deployments)}")
        logger.info(f"Found ArgoCD statefulsets: {', '.join(statefulsets)}")
        
        # Track which resources have been verified as ready
        ready_resources: Set[str] = set()
        total_resources = set(deployments + statefulsets)
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            # Check deployments
            for deployment in deployments:
                if deployment in ready_resources:
                    continue
                    
                if self._check_deployment_ready(deployment):
                    ready_resources.add(deployment)
                    logger.info(f"Deployment {deployment} is ready")
            
            # Check statefulsets
            for statefulset in statefulsets:
                if statefulset in ready_resources:
                    continue
                    
                if self._check_statefulset_ready(statefulset):
                    ready_resources.add(statefulset)
                    logger.info(f"StatefulSet {statefulset} is ready")
            
            # Check if all resources are ready
            if ready_resources == total_resources:
                logger.info("All ArgoCD pods are ready")
                return True
            
            # Not all ready yet, continue waiting
            resources_left = len(total_resources) - len(ready_resources)
            logger.debug(f"Waiting for {resources_left} more ArgoCD resources to be ready...")
            time.sleep(5)
        
        # Timeout reached
        not_ready = total_resources - ready_resources
        logger.error(f"Timeout waiting for ArgoCD pods to be ready. Resources not ready: {', '.join(not_ready)}")
        return False
    
    def restart_repo_server(self) -> bool:
        """Restart the Argo CD repo server deployment.
        
        Returns:
            bool: True if restart was successful, False otherwise
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        try:
            logger.info("Restarting ArgoCD repo server deployment...")
            result = subprocess.run(
                [self.kubectl_path, "rollout", "restart", "deployment/argocd-repo-server", "-n", "argocd"],
                env=self.env,
                check=True,
                capture_output=True
            )
            logger.info(f"Restarted repo server: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart repo server: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Error restarting repo server: {str(e)}")
            return False
    
    def restart_application_controller(self) -> bool:
        """Restart the Argo CD application controller statefulset.
        
        For StatefulSets, we need to delete the pod and let the controller recreate it.
        
        Returns:
            bool: True if restart was successful, False otherwise
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
            
        try:
            logger.info("Restarting ArgoCD application controller pod...")
            result = subprocess.run(
                [self.kubectl_path, "delete", "pod", "argocd-application-controller-0", "-n", "argocd"],
                env=self.env,
                check=True,
                capture_output=True
            )
            logger.info(f"Deleted application controller pod: {result.stdout.decode().strip()}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart application controller: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Error restarting application controller: {str(e)}")
            return False
    
    def wait_for_repo_server_ready(self, timeout_seconds: int = 120) -> bool:
        """Wait for the repo server pods to be ready.
        
        Args:
            timeout_seconds: Timeout in seconds
            
        Returns:
            bool: True if pods are ready, False if timeout
        """
        return self._wait_for_deployment_ready("argocd-repo-server", timeout_seconds)
    
    def wait_for_application_controller_ready(self, timeout_seconds: int = 120) -> bool:
        """Wait for the application controller pod to be ready.
        
        Args:
            timeout_seconds: Timeout in seconds
            
        Returns:
            bool: True if pod is ready, False if timeout
        """
        return self._wait_for_statefulset_ready("argocd-application-controller", timeout_seconds)
    
    def _check_deployment_ready(self, deployment_name: str) -> bool:
        """Check if a deployment is ready without waiting.
        
        Args:
            deployment_name: Name of the deployment
            
        Returns:
            bool: True if deployment is ready
        """
        if not self.kubectl_path:
            return False
            
        try:
            # Check deployment status
            result = subprocess.run(
                [self.kubectl_path, "get", "deployment", deployment_name, "-n", "argocd", 
                 "-o", "jsonpath='{.status.readyReplicas}/{.status.replicas}'"],
                env=self.env,
                check=True,
                capture_output=True
            )
            
            status = result.stdout.decode().strip("'")
            
            # Handle empty status gracefully
            if not status or "/" not in status:
                return False
                
            try:
                ready, total = map(int, status.split("/"))
                return ready == total and total > 0
            except ValueError:
                # Handle parse errors gracefully
                return False
                
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False
    
    def _check_statefulset_ready(self, statefulset_name: str) -> bool:
        """Check if a statefulset is ready without waiting.
        
        Args:
            statefulset_name: Name of the statefulset
            
        Returns:
            bool: True if statefulset is ready
        """
        if not self.kubectl_path:
            return False
            
        try:
            # Check statefulset status
            result = subprocess.run(
                [self.kubectl_path, "get", "statefulset", statefulset_name, "-n", "argocd", 
                 "-o", "jsonpath='{.status.readyReplicas}/{.status.replicas}'"],
                env=self.env,
                check=True,
                capture_output=True
            )
            
            status = result.stdout.decode().strip("'")
            
            # Handle empty status gracefully
            if not status or "/" not in status:
                return False
                
            try:
                ready, total = map(int, status.split("/"))
                if ready != total or total == 0:
                    return False
                    
                # Now check that all containers in all pods are ready
                pods_result = subprocess.run(
                    [self.kubectl_path, "get", "pods", "-n", "argocd", 
                     "-l", f"app.kubernetes.io/name={statefulset_name}", 
                     "-o", "jsonpath='{range .items[*]}{.metadata.name}:{range .status.containerStatuses[*]}{.ready}{end}{\"\\n\"}{end}'"],
                    env=self.env,
                    check=True,
                    capture_output=True
                )
                
                pods_status = pods_result.stdout.decode().strip("'").strip()
                if not pods_status:
                    return False
                    
                for line in pods_status.split("\n"):
                    if line and "false" in line:
                        return False
                        
                return True
                
            except ValueError:
                # Handle parse errors gracefully
                return False
                
        except subprocess.CalledProcessError:
            return False
        except Exception:
            return False
    
    def _wait_for_deployment_ready(self, deployment_name: str, timeout_seconds: int = 120) -> bool:
        """Wait for a deployment to be ready.
        
        Args:
            deployment_name: Name of the deployment
            timeout_seconds: Timeout in seconds
            
        Returns:
            bool: True if deployment is ready, False if timeout
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
        
        logger.info(f"Waiting for deployment {deployment_name} to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                # Check deployment status
                result = subprocess.run(
                    [self.kubectl_path, "get", "deployment", deployment_name, "-n", "argocd", 
                     "-o", "jsonpath='{.status.readyReplicas}/{.status.replicas}'"],
                    env=self.env,
                    check=True,
                    capture_output=True
                )
                
                status = result.stdout.decode().strip("'")
                
                # Handle empty status gracefully
                if not status or "/" not in status:
                    logger.debug(f"Deployment {deployment_name} not fully initialized yet, waiting...")
                    time.sleep(2)
                    continue
                
                try:
                    ready, total = map(int, status.split("/"))
                    if ready == total and total > 0:
                        logger.info(f"Deployment {deployment_name} is ready ({ready}/{total} replicas)")
                        return True
                        
                    logger.debug(f"Deployment {deployment_name} status: {ready}/{total} replicas, waiting...")
                except ValueError:
                    # Handle parse errors gracefully
                    logger.debug(f"Deployment {deployment_name} returned status '{status}', waiting for initialization...")
                
                time.sleep(2)
                
            except subprocess.CalledProcessError as e:
                logger.debug(f"Error checking deployment {deployment_name}: {e.stderr.decode()}")
                time.sleep(5)
            except Exception as e:
                logger.debug(f"Waiting for deployment {deployment_name} to initialize: {str(e)}")
                time.sleep(5)
        
        logger.error(f"Timeout waiting for deployment {deployment_name} to be ready")
        return False
    
    def _wait_for_statefulset_ready(self, statefulset_name: str, timeout_seconds: int = 120) -> bool:
        """Wait for a statefulset to be ready.
        
        Args:
            statefulset_name: Name of the statefulset
            timeout_seconds: Timeout in seconds
            
        Returns:
            bool: True if statefulset is ready, False if timeout
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return False
        
        logger.info(f"Waiting for statefulset {statefulset_name} to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            try:
                # First check statefulset status
                result = subprocess.run(
                    [self.kubectl_path, "get", "statefulset", statefulset_name, "-n", "argocd", 
                     "-o", "jsonpath='{.status.readyReplicas}/{.status.replicas}'"],
                    env=self.env,
                    check=True,
                    capture_output=True
                )
                
                status = result.stdout.decode().strip("'")
                
                # Handle empty status gracefully
                if not status or "/" not in status:
                    logger.debug(f"Statefulset {statefulset_name} not fully initialized yet, waiting...")
                    time.sleep(2)
                    continue
                
                try:
                    ready, total = map(int, status.split("/"))
                    if ready == total and total > 0:
                        # Now check that all containers in all pods are ready
                        pods_result = subprocess.run(
                            [self.kubectl_path, "get", "pods", "-n", "argocd", 
                             "-l", f"app.kubernetes.io/name={statefulset_name}", 
                             "-o", "jsonpath='{range .items[*]}{.metadata.name}:{range .status.containerStatuses[*]}{.ready}{end}{\"\\n\"}{end}'"],
                            env=self.env,
                            check=True,
                            capture_output=True
                        )
                        
                        pods_status = pods_result.stdout.decode().strip("'").strip()
                        all_containers_ready = True
                        
                        if pods_status:
                            for line in pods_status.split("\n"):
                                if line and "false" in line:
                                    all_containers_ready = False
                                    logger.debug(f"Some containers in {statefulset_name} pods are not ready, waiting...")
                                    break
                        else:
                            all_containers_ready = False
                            logger.debug(f"No pods found for {statefulset_name}, waiting...")
                        
                        if all_containers_ready:
                            logger.info(f"Statefulset {statefulset_name} is ready ({ready}/{total} replicas)")
                            return True
                    else:
                        logger.debug(f"Statefulset {statefulset_name} status: {ready}/{total} replicas, waiting...")
                except ValueError:
                    # Handle parse errors gracefully
                    logger.debug(f"Statefulset {statefulset_name} returned status '{status}', waiting for initialization...")
                
                time.sleep(2)
                
            except subprocess.CalledProcessError as e:
                logger.debug(f"Error checking statefulset {statefulset_name}: {e.stderr.decode()}")
                time.sleep(5)
            except Exception as e:
                logger.debug(f"Waiting for statefulset {statefulset_name} to initialize: {str(e)}")
                time.sleep(5)
        
        logger.error(f"Timeout waiting for statefulset {statefulset_name} to be ready")
        return False
        
    def restart_argocd_components(self) -> bool:
        """Restart Argo CD components that handle repository access.
        
        This method restarts the repo server and application controller,
        then waits for them to be ready.
        
        Returns:
            bool: True if all components were restarted and are ready, False otherwise
        """
        logger.info("Restarting Argo CD components to refresh repository configuration...")
        
        # Restart the repo server
        if not self.restart_repo_server():
            logger.error("Failed to restart repo server")
            return False
            
        # Wait for repo server to be ready
        if not self.wait_for_repo_server_ready():
            logger.error("Repo server failed to become ready after restart")
            return False
            
        # Restart the application controller
        if not self.restart_application_controller():
            logger.error("Failed to restart application controller")
            return False
            
        # Wait for application controller to be ready
        if not self.wait_for_application_controller_ready():
            logger.error("Application controller failed to become ready after restart")
            return False
            
        logger.info("All Argo CD components have been restarted and are ready")
        return True