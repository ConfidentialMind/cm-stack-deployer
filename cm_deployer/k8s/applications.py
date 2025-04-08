import logging
import subprocess
import yaml
import tempfile
import os
from pathlib import Path
from typing import Dict, Optional, Any, List

from cm_deployer.templates import get_template_path

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
        """Create or update the Dependencies application using template with parameters.
        
        Args:
            values: Dictionary of values to pass to the Helm chart
            target_revision: Target revision for the git repository (branch, tag, or commit)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Creating/updating Dependencies application")
        
        try:
            # Get template path
            template_path = get_template_path("argocd/cm-stack-dependencies-root-app.yaml")
            
            # Read template content
            template_content = template_path.read_text()
            
            # Replace placeholders directly since this is a simple template
            manifest_yaml = template_content
            
            # Replace targetRevision
            manifest_yaml = manifest_yaml.replace("{targetRevision}", target_revision)
            
            # Replace deploy.cert_manager
            cert_manager_value = 'true' if values.get('deploy', {}).get('cert_manager', False) else 'false'
            manifest_yaml = manifest_yaml.replace("{deploy.cert_manager}", cert_manager_value)
            
            # Replace deploy.longhorn_csi
            longhorn_value = 'true' if values.get('deploy', {}).get('longhorn_csi', False) else 'false'
            manifest_yaml = manifest_yaml.replace("{deploy.longhorn_csi}", longhorn_value)
            
            # Replace deploy.nvidia_plugin
            nvidia_value = 'true' if values.get('deploy', {}).get('nvidia_plugin', False) else 'false'
            manifest_yaml = manifest_yaml.replace("{deploy.nvidia_plugin}", nvidia_value)
            
            # Parse manifest
            manifest = yaml.safe_load(manifest_yaml)
            
            logger.debug(f"Dependencies application manifest: {manifest}")
            return self.apply_manifest(manifest)
        except Exception as e:
            logger.error(f"Error creating Dependencies application: {str(e)}")
            return False

    def create_base_app(self, values: Dict[str, Any], target_revision: str = "HEAD") -> bool:
        """Create or update the Base application using template with explicit parameters.
        
        Args:
            values: Dictionary of values to pass to the Helm chart
            target_revision: Target revision for the git repository (branch, tag, or commit)
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Creating/updating Base application")
        
        try:
            # Get template path
            template_path = get_template_path("argocd/cm-stack-base.yaml")
            
            # Read template content
            template_content = template_path.read_text()
            
            # Replace targetRevision
            template_content = template_content.replace("{targetRevision}", target_revision)
            
            # Load defaults
            defaults_path = Path(__file__).parent.parent / "config" / "defaults.yaml"
            defaults = {}
            if defaults_path.exists():
                with open(defaults_path, 'r') as f:
                    defaults = yaml.safe_load(f)
                logger.debug("Loaded defaults from defaults.yaml")
            else:
                logger.warning(f"Defaults file not found at {defaults_path}")
            
            # Merge defaults with provided values (values take precedence)
            merged_values = self._deep_merge(defaults, values)
            
            # Create a copy of the manifest for modification
            manifest_yaml = template_content
            
            # Helper function to format multi-line values with consistent indentation
            def format_multiline_value(value):
                """Format a multi-line value for YAML with consistent indentation.
                
                This preserves the content but ensures each line after the first has
                the same indentation.
                """
                if not value or not isinstance(value, str):
                    return ""
                
                # Split the string into lines
                lines = value.strip().split('\n')
                
                # Join with newlines and consistent indentation (matching the template)
                return "\n            ".join(lines)
                
            # Helper function to properly format parameter values
            def format_value(value):
                """Format a value for use in Helm parameters."""
                if value is None:
                    return ""
                    
                if isinstance(value, bool):
                    return str(value).lower()
                    
                # Multi-line strings need special handling for parameters
                if isinstance(value, str) and '\n' in value:
                    # Replace newlines with literal \n for parameters
                    return value.replace('\n', '\\n').replace('"', '\\"')
                    
                return str(value)
            
            # Helper function to get a formatted value from the merged dictionary
            def get_formatted_value(path):
                """Get formatted value from nested dictionary using dot notation path."""
                parts = path.split('.')
                current = merged_values
                
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        return ""
                
                return format_value(current)
            
            # Multi-line values that need special formatting
            multiline_values = [
                'tls.ownCert.fullchainCertificate',
                'tls.ownCert.privateKey',
                'secrets.cmStackMainRepoKey',
                'secrets.cmImageRegistryAuth',
                'istio.jwkConfig'
            ]
            
            # Process multi-line values
            for value_path in multiline_values:
                parts = value_path.split('.')
                current = merged_values
                
                # Navigate to the value
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        current = ""
                        break
                
                # Format the value if it's a string
                if isinstance(current, str):
                    formatted_value = format_multiline_value(current)
                    manifest_yaml = manifest_yaml.replace(f"{{{value_path}}}", formatted_value)
            
            # Replace all other placeholders in the template
            placeholders = [
                'base_domain',
                'tls.enabled',
                'tls.certManager.enabled',
                'tls.certManager.email',
                'tls.ownCert.useOwnCert',
                'db.backup.enabled',
                'db.backup.volumeSnapshot.className',
                'db.backup.retentionPolicy',
                'db.backup.schedule'
            ]
            
            for placeholder in placeholders:
                value = get_formatted_value(placeholder)
                manifest_yaml = manifest_yaml.replace(f"{{{placeholder}}}", value)
            
            # Parse the manifest
            manifest = yaml.safe_load(manifest_yaml)
            
            logger.debug(f"Base application manifest: {manifest}")
            return self.apply_manifest(manifest)
        except Exception as e:
            logger.error(f"Error creating Base application: {str(e)}")
            return False
           
    def _deep_merge(self, source: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries, with override values taking precedence.
        
        Args:
            source: Source dictionary
            override: Override dictionary with values that take precedence
            
        Returns:
            Dict[str, Any]: Merged dictionary
        """
        result = source.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self._deep_merge(result[key], value)
            else:
                # Override or add the key
                result[key] = value
                
        return result
    
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