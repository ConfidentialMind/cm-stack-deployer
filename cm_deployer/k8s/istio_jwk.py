import base64
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class IstioJWKResourceProvisioner:
    """Class for provisioning JWK resources for Istio JWT authentication in Kubernetes."""
    
    def __init__(self, kubeconfig: Optional[Path] = None):
        """Initialize Istio JWK resource provisioner.
        
        Args:
            kubeconfig: Path to kubeconfig file (for Kubernetes operations)
        """
        self.kubeconfig = kubeconfig
        
        # Prepare environment with kubeconfig
        self.env = os.environ.copy()
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
    
    def provision_resources(self, private_key: str, jwk: str) -> bool:
        """Provision Kubernetes resources for Istio JWT authentication.
        
        Creates:
        - Secret with private key in api-services namespace
        - ConfigMap with JWK in istio-system namespace
        
        Args:
            private_key: Private key content as string
            jwk: JWK content as string
            
        Returns:
            bool: True if provisioning was successful
        """
        from kubernetes import client, config
        
        try:
            # Load Kubernetes configuration
            if self.kubeconfig:
                config.load_kube_config(config_file=str(self.kubeconfig))
            else:
                config.load_kube_config()
            
            # Create api-services namespace if it doesn't exist
            self._create_namespace("api-services")
            
            # Create Secret for private key
            api_instance = client.CoreV1Api()
            
            # Create Secret for private key
            secret_body = client.V1Secret(
                api_version="v1",
                kind="Secret",
                metadata=client.V1ObjectMeta(
                    name="private-key-secret",
                    namespace="api-services"
                ),
                data={
                    "private.pem": self._encode_base64(private_key)
                }
            )
            
            # Create or update the Secret
            try:
                api_instance.create_namespaced_secret(
                    namespace="api-services",
                    body=secret_body
                )
                logger.info("Created private key Secret")
            except client.rest.ApiException as e:
                if e.status == 409:  # Conflict, already exists
                    api_instance.replace_namespaced_secret(
                        name="private-key-secret",
                        namespace="api-services",
                        body=secret_body
                    )
                    logger.info("Updated private key Secret")
                else:
                    raise
            
            # Create ConfigMap for JWK
            config_map_body = client.V1ConfigMap(
                api_version="v1",
                kind="ConfigMap",
                metadata=client.V1ObjectMeta(
                    name="jwk-config",
                    namespace="istio-system",
                    annotations={
                        "cm-deployment-note": "This config map contains the JWK for Istio JWT authentication. It is passed to applications via helm variables."
                    }
                ),
                data={
                    "jwk": jwk
                }
            )
            
            # Create istio-system namespace if it doesn't exist
            self._create_namespace("istio-system")
            
            # Create or update the ConfigMap
            try:
                api_instance.create_namespaced_config_map(
                    namespace="istio-system",
                    body=config_map_body
                )
                logger.info("Created JWK ConfigMap in istio-system namespace")
            except client.rest.ApiException as e:
                if e.status == 409:  # Conflict, already exists
                    api_instance.replace_namespaced_config_map(
                        name="jwk-config",
                        namespace="istio-system",
                        body=config_map_body
                    )
                    logger.info("Updated JWK ConfigMap in istio-system namespace")
                else:
                    raise
            
            return True
            
        except Exception as e:
            logger.error(f"Error provisioning Istio JWK resources: {str(e)}")
            return False
    
    def _create_namespace(self, namespace: str) -> bool:
        """Create a Kubernetes namespace if it doesn't exist."""
        from kubernetes import client
        
        api_instance = client.CoreV1Api()
        
        try:
            api_instance.read_namespace(namespace)
            logger.debug(f"Namespace {namespace} already exists")
            return True
        except client.rest.ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist, create it
                namespace_body = client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=namespace
                    )
                )
                
                try:
                    api_instance.create_namespace(body=namespace_body)
                    logger.info(f"Created namespace {namespace}")
                    return True
                except Exception as e:
                    logger.error(f"Error creating namespace {namespace}: {str(e)}")
                    return False
            else:
                logger.error(f"Error checking namespace {namespace}: {str(e)}")
                return False
    
    def _encode_base64(self, data: str) -> str:
        """Encode string to base64 as required by Kubernetes secrets."""
        return base64.b64encode(data.encode()).decode()