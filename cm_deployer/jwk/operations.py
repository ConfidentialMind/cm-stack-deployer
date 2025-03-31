import base64
import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import hashlib
import uuid

logger = logging.getLogger(__name__)

class JWKGenerator:
    """Class for generating and managing JWK (JSON Web Key) operations using pure Python."""
    
    def __init__(self, base_dir: Path, kubeconfig: Optional[Path] = None):
        """Initialize JWK generator.
        
        Args:
            base_dir: Base directory where JWK files will be stored
            kubeconfig: Path to kubeconfig file (for Kubernetes operations)
        """
        self.base_dir = base_dir
        self.kubeconfig = kubeconfig
        self.jwk_path = base_dir / "jwks.json"
        self.private_key_path = base_dir / "private-key.pem"
        
        # Prepare environment with kubeconfig
        self.env = os.environ.copy()
        if kubeconfig:
            self.env["KUBECONFIG"] = str(kubeconfig)
    
    def check_jwk_files_exist(self) -> bool:
        """Check if JWK files already exist.
        
        Returns:
            bool: True if both jwks.json and private-key.pem exist
        """
        jwk_exists = self.jwk_path.exists()
        key_exists = self.private_key_path.exists()
        
        logger.debug(f"JWK file exists: {jwk_exists}, Private key exists: {key_exists}")
        return jwk_exists and key_exists
    
    def generate_jwk(self) -> bool:
        """Generate JWK files if they don't exist.
        
        Returns:
            bool: True if generation was successful or files already exist
        """
        # Check if files already exist
        if self.check_jwk_files_exist():
            logger.info("JWK files already exist, skipping generation")
            return True
        
        # Create directory if it doesn't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            logger.info("Generating private RSA key...")
            # Generate a new RSA private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,  # Standard value for exponent
                key_size=2048,           # 2048 bits for good security
                backend=default_backend()
            )
            
            # Serialize the private key to PEM format
            pem_private_key = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ).decode('utf-8')
            
            # Save the private key to file
            self.private_key_path.write_text(pem_private_key)
            
            # Generate JWK from private key
            logger.info("Converting private key to JWK format...")
            jwk = self._private_key_to_jwk(private_key)
            
            # Create a JWKS (JSON Web Key Set) with the JWK
            jwks = {"keys": [jwk]}
            
            # Save the JWKS to file
            self.jwk_path.write_text(json.dumps(jwks, indent=2))
            
            logger.info("JWK generation completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error generating JWK: {str(e)}")
            return False
    
    def _private_key_to_jwk(self, private_key) -> Dict[str, Any]:
        """Convert an RSA private key to JWK format.
        
        Args:
            private_key: RSA private key object
            
        Returns:
            dict: JWK representation of the key
        """
        # Get the public numbers
        public_numbers = private_key.public_key().public_numbers()
        
        # Get the private numbers
        private_numbers = private_key.private_numbers()
        
        # Generate a key ID
        kid = self._generate_kid()
        
        # Convert integers to base64url encoded strings
        def int_to_base64url(value):
            """Convert an integer to a base64url-encoded string."""
            bytes_value = value.to_bytes((value.bit_length() + 7) // 8, byteorder='big')
            return base64.urlsafe_b64encode(bytes_value).rstrip(b'=').decode('ascii')
        
        # Create the JWK
        jwk = {
            "kty": "RSA",
            "use": "sig",
            "alg": "RS256",
            "kid": kid,
            # Public key components
            "n": int_to_base64url(public_numbers.n),  # Modulus
            "e": int_to_base64url(public_numbers.e),  # Public exponent
            # Private key components
            "d": int_to_base64url(private_numbers.d),  # Private exponent
            "p": int_to_base64url(private_numbers.p),  # First prime factor
            "q": int_to_base64url(private_numbers.q),  # Second prime factor
            "dp": int_to_base64url(private_numbers.dmp1),  # First factor CRT exponent
            "dq": int_to_base64url(private_numbers.dmq1),  # Second factor CRT exponent
            "qi": int_to_base64url(private_numbers.iqmp),  # CRT coefficient
        }
        
        return jwk
    
    def _generate_kid(self) -> str:
        """Generate a Key ID (kid) for the JWK.
        
        Returns:
            str: A unique key ID
        """
        # Use a UUID4 for uniqueness
        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]
    
    def read_jwk_files(self) -> Tuple[Optional[str], Optional[str]]:
        """Read the content of JWK files.
        
        Returns:
            tuple: (private_key_content, jwk_content) or (None, None) if files don't exist
        """
        if not self.check_jwk_files_exist():
            logger.error("JWK files don't exist, cannot read content")
            return None, None
        
        try:
            private_key = self.private_key_path.read_text()
            jwk = self.jwk_path.read_text()
            return private_key, jwk
        except Exception as e:
            logger.error(f"Error reading JWK files: {str(e)}")
            return None, None
    
    def create_kubernetes_resources(self, private_key: str, jwk: str) -> bool:
        """Create Kubernetes Secret and ConfigMap for JWK.
        
        Args:
            private_key: Content of the private key
            jwk: Content of the JWK
            
        Returns:
            bool: True if creation was successful
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
                        "cm-deployment-note": "This config map is inert. It is used to store the JWK for the JWT token. The JWK is passed to the application via helm variables."
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
                logger.info("Created JWK ConfigMap")
            except client.rest.ApiException as e:
                if e.status == 409:  # Conflict, already exists
                    api_instance.replace_namespaced_config_map(
                        name="jwk-config",
                        namespace="istio-system",
                        body=config_map_body
                    )
                    logger.info("Updated JWK ConfigMap")
                else:
                    raise
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating Kubernetes resources for JWK: {str(e)}")
            return False
    
    def _create_namespace(self, namespace: str) -> bool:
        """Create a Kubernetes namespace if it doesn't exist.
        
        Args:
            namespace: Name of the namespace
            
        Returns:
            bool: True if creation was successful or namespace already exists
        """
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
        """Encode string to base64 as required by Kubernetes secrets.
        
        Args:
            data: String to encode
            
        Returns:
            str: Base64 encoded string
        """
        return base64.b64encode(data.encode()).decode()
