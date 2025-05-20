from pathlib import Path
import json
import logging
from typing import Dict, Any, Tuple

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from authlib.jose import JsonWebKey

# Get logger
logger = logging.getLogger(__name__)


class JWKGenerator:
    """Class for generating JWK (JSON Web Key) files."""
    
    # Original header as a constant
    HEADER = {
        "alg": "RS256",
        "typ": "JWT",
        "kid": "api-key"
    }
    
    def __init__(self, base_dir: Path):
        """Initialize JWK generator.
        
        Args:
            base_dir: Base directory where JWK files will be stored
        """
        self.base_dir = base_dir
        self.jwk_path = base_dir / "jwks.json"
        self.private_key_path = base_dir / "private-key.pem"
        self.public_key_path = base_dir / "public-key.pem"
        
        # Create base directory if it doesn't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"JWKGenerator initialized with base_dir: {base_dir}")
    
    def generate_rsa_key_pair(self) -> rsa.RSAPrivateKey:
        """Generate RSA key pair and save to files.
        
        Returns:
            The generated RSA private key
        """
        logger.debug("Generating new RSA key pair")
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Save private key
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        self.private_key_path.write_bytes(private_pem)
        logger.debug(f"Private key saved to {self.private_key_path}")
        
        # Save public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.public_key_path.write_bytes(public_pem)
        logger.debug(f"Public key saved to {self.public_key_path}")
        
        return private_key
    
    def create_jwk(self, private_key: rsa.RSAPrivateKey) -> Dict[str, Any]:
        """Create JWK from private key.
        
        Args:
            private_key: RSA private key
            
        Returns:
            The JWK as a dictionary
        """
        logger.debug("Creating JWK from private key")
        
        # Extract public key and convert to PEM format first
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        logger.debug("Converting public key to JWK")
        # Create JWK from PEM-formatted public key
        try:
            # Using PEM instead of direct key object
            jwk = JsonWebKey.import_key(public_pem)
            jwk_dict = jwk.as_dict()
            
            logger.debug("Adding header parameters to JWK")
            # Add additional parameters from header
            jwk_dict.update({
                "use": "sig",
                "alg": self.HEADER["alg"],
                "typ": self.HEADER["typ"],
                "kid": self.HEADER["kid"]
            })
            
            return jwk_dict
        except Exception as e:
            logger.error(f"Error creating JWK: {e}")
            logger.debug(f"Public key type: {type(public_key)}")
            logger.debug(f"Public PEM type: {type(public_pem)}")
            raise
    
    def generate_jwk(self) -> Dict[str, Any]:
        """Generate JWK and save it to file.
        
        Returns:
            The JWKS as a dictionary
        """
        # Check if private key exists
        if self.private_key_path.exists():
            logger.debug(f"Loading existing private key from {self.private_key_path}")
            try:
                # Load existing private key
                with open(self.private_key_path, "rb") as f:
                    private_key = serialization.load_pem_private_key(
                        f.read(),
                        password=None
                    )
            except Exception as e:
                logger.error(f"Error loading private key: {e}")
                logger.debug("Generating new key pair instead")
                private_key = self.generate_rsa_key_pair()
        else:
            logger.debug("Private key does not exist, generating new key pair")
            # Generate new key pair
            private_key = self.generate_rsa_key_pair()
        
        # Create JWK
        logger.debug("Creating JWK")
        jwk_dict = self.create_jwk(private_key)
        
        # Create JWKS
        logger.debug("Creating JWKS")
        jwks = {"keys": [jwk_dict]}
        
        # Save JWKS to file
        logger.debug(f"Saving JWKS to {self.jwk_path}")
        with open(self.jwk_path, "w") as f:
            json.dump(jwks, f, indent=2)
        
        return jwks

    def read_jwk_files(self) -> Tuple[bytes, Dict[str, Any]]:
        """Read JWK files.
        
        Returns:
            Tuple containing (private_key_pem, jwk_dict)
        """
        logger.debug(f"Reading JWK files from {self.base_dir}")
        
        # Check if files exist
        if not self.private_key_path.exists():
            logger.error(f"Private key file not found: {self.private_key_path}")
            return None, None
            
        if not self.jwk_path.exists():
            logger.error(f"JWKS file not found: {self.jwk_path}")
            return None, None
        
        # Read private key
        logger.debug(f"Reading private key from {self.private_key_path}")
        private_key_pem = self.private_key_path.read_bytes()
        
        # Read JWK JSON
        logger.debug(f"Reading JWKS from {self.jwk_path}")
        with open(self.jwk_path, "r") as f:
            jwks_json = json.load(f)
        
        # Return just the private key and the JWK dictionary
        return private_key_pem, jwks_json