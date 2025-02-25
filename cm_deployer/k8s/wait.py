import logging
import time
import subprocess
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

class ArgoCDAppWaiter:
    """Class for waiting on ArgoCD application status."""
    
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize with optional kubeconfig path."""
        # Start with current environment
        self.env = os.environ.copy()
        
        # Add kubeconfig if provided
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
            logger.debug(f"ArgoCDAppWaiter using kubeconfig: {kubeconfig}")
            
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
    
    def get_app_status(self, app_name: str, namespace: str = "argocd") -> Dict[str, Any]:
        """Get the current status of an ArgoCD application.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            
        Returns:
            dict: Application status as a dictionary
        """
        if not self.kubectl_path:
            logger.error("kubectl command not found. Please ensure kubectl is installed and in PATH")
            return {}
            
        try:
            result = subprocess.run(
                [self.kubectl_path, "get", "application", app_name, "-n", namespace, "-o", "json"],
                env=self.env,
                check=True,
                capture_output=True
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get application status: {e.stderr.decode()}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse application status: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Error getting application status: {str(e)}")
            return {}
    
    def is_app_synced(self, app_name: str, namespace: str = "argocd") -> bool:
        """Check if an application is synced.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            
        Returns:
            bool: True if the application is synced, False otherwise
        """
        status = self.get_app_status(app_name, namespace)
        if not status:
            return False
        
        try:
            sync_status = status.get("status", {}).get("sync", {}).get("status")
            is_synced = sync_status == "Synced"
            
            if not is_synced:
                logger.info(f"Application {app_name} sync status: {sync_status}")
                
            return is_synced
        except (KeyError, AttributeError) as e:
            logger.error(f"Error checking sync status: {str(e)}")
            return False
    
    def is_app_healthy(self, app_name: str, namespace: str = "argocd") -> bool:
        """Check if an application is healthy.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            
        Returns:
            bool: True if the application is healthy, False otherwise
        """
        status = self.get_app_status(app_name, namespace)
        if not status:
            return False
        
        try:
            health_status = status.get("status", {}).get("health", {}).get("status")
            is_healthy = health_status == "Healthy"
            
            if not is_healthy:
                logger.info(f"Application {app_name} health status: {health_status}")
                
            return is_healthy
        except (KeyError, AttributeError) as e:
            logger.error(f"Error checking health status: {str(e)}")
            return False
    
    def get_app_resources(self, app_name: str, namespace: str = "argocd") -> List[Dict[str, Any]]:
        """Get the resources of an ArgoCD application.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            
        Returns:
            list: List of resources
        """
        status = self.get_app_status(app_name, namespace)
        if not status:
            return []
        
        try:
            resources = status.get("status", {}).get("resources", [])
            return resources
        except (KeyError, AttributeError) as e:
            logger.error(f"Error getting resources: {str(e)}")
            return []
    
    def wait_for_app_sync(self, app_name: str, namespace: str = "argocd", 
                         timeout_seconds: int = 600, interval_seconds: int = 10) -> bool:
        """Wait for an application to be synced.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            timeout_seconds: Maximum time to wait in seconds
            interval_seconds: Time between checks in seconds
            
        Returns:
            bool: True if the application is synced, False if timeout
        """
        logger.info(f"Waiting for application {app_name} to be synced (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.is_app_synced(app_name, namespace):
                logger.info(f"Application {app_name} is synced")
                return True
            
            elapsed = int(time.time() - start_time)
            remaining = timeout_seconds - elapsed
            logger.info(f"Waiting for application {app_name} to be synced... ({elapsed}s elapsed, {remaining}s remaining)")
            time.sleep(interval_seconds)
        
        logger.error(f"Timeout waiting for application {app_name} to be synced")
        self._log_app_status(app_name, namespace)
        return False
    
    def wait_for_app_health(self, app_name: str, namespace: str = "argocd", 
                           timeout_seconds: int = 600, interval_seconds: int = 10) -> bool:
        """Wait for an application to be healthy.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            timeout_seconds: Maximum time to wait in seconds
            interval_seconds: Time between checks in seconds
            
        Returns:
            bool: True if the application is healthy, False if timeout
        """
        logger.info(f"Waiting for application {app_name} to be healthy (timeout: {timeout_seconds}s)...")
        
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if self.is_app_healthy(app_name, namespace):
                logger.info(f"Application {app_name} is healthy")
                return True
            
            elapsed = int(time.time() - start_time)
            remaining = timeout_seconds - elapsed
            logger.info(f"Waiting for application {app_name} to be healthy... ({elapsed}s elapsed, {remaining}s remaining)")
            time.sleep(interval_seconds)
        
        logger.error(f"Timeout waiting for application {app_name} to be healthy")
        self._log_app_status(app_name, namespace)
        return False
    
    def wait_for_app_ready(self, app_name: str, namespace: str = "argocd",
                          timeout_seconds: int = 1200, interval_seconds: int = 10) -> bool:
        """Wait for an application to be both synced and healthy.
        
        Args:
            app_name: Name of the ArgoCD application
            namespace: Namespace where the application is located
            timeout_seconds: Maximum time to wait in seconds
            interval_seconds: Time between checks in seconds
            
        Returns:
            bool: True if the application is ready, False if timeout
        """
        # Split the timeout between sync and health
        sync_timeout = timeout_seconds // 2
        health_timeout = timeout_seconds - sync_timeout
        
        if not self.wait_for_app_sync(app_name, namespace, sync_timeout, interval_seconds):
            return False
        
        return self.wait_for_app_health(app_name, namespace, health_timeout, interval_seconds)
    
    def _log_app_status(self, app_name: str, namespace: str = "argocd") -> None:
        """Log detailed application status for debugging."""
        status = self.get_app_status(app_name, namespace)
        if not status:
            logger.error(f"Could not get status for application {app_name}")
            return
        
        try:
            sync_status = status.get("status", {}).get("sync", {}).get("status", "Unknown")
            health_status = status.get("status", {}).get("health", {}).get("status", "Unknown")
            
            logger.error(f"Application {app_name} status: Sync={sync_status}, Health={health_status}")
            
            # Log resource status
            resources = self.get_app_resources(app_name, namespace)
            if resources:
                logger.error(f"Application resources:")
                for resource in resources:
                    kind = resource.get("kind", "Unknown")
                    name = resource.get("name", "Unknown")
                    health = resource.get("health", {}).get("status", "Unknown")
                    sync = resource.get("status", "Unknown")
                    logger.error(f"  {kind}/{name}: Health={health}, Sync={sync}")
        except Exception as e:
            logger.error(f"Error logging application status: {str(e)}")
