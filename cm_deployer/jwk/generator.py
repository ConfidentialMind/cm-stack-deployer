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
    """Class for generating and managing JWK (JSON Web Key) files."""
    
    def __init__(self, base_dir: Path):
        """Initialize JWK generator.
        
        Args:
            base_dir: Base directory where JWK files will be stored
        """
        self.base_dir = base_dir
        self.jwk_path = base_dir / "jwks.json"
        self.private_key_path = base_dir / "private-key.pem"
        
    def check_jwk_files_exist(self) -> bool:
        """Check if JWK files already exist."""
        jwk_exists = self.jwk_path.exists()
        key_exists = self.private_key_path.exists()
        
        logger.debug(f"JWK file exists: {jwk_exists}, Private key exists: {key_exists}")
        return jwk_exists and key_exists
    
    def generate_jwk(self) -> bool:
        """Generate JWK files if they don't exist."""
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
                key_size=2048,          # 2048 bits for good security
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
        """Convert an RSA private key to JWK format."""
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
        """Generate a Key ID (kid) for the JWK."""
        # Use a UUID4 for uniqueness
        return hashlib.sha256(uuid.uuid4().bytes).hexdigest()[:16]
    
    def read_jwk_files(self) -> Tuple[Optional[str], Optional[str]]:
        """Read the content of JWK files."""
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