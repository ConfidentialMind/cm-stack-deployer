from pathlib import Path
import json
from typing import Dict, Any

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from authlib.jose import JsonWebKey


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
    
    def generate_rsa_key_pair(self) -> rsa.RSAPrivateKey:
        """Generate RSA key pair and save to files.
        
        Returns:
            The generated RSA private key
        """
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
        
        # Save public key
        public_key = private_key.public_key()
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.public_key_path.write_bytes(public_pem)
        
        return private_key
    
    def create_jwk(self, private_key: rsa.RSAPrivateKey) -> Dict[str, Any]:
        """Create JWK from private key.
        
        Args:
            private_key: RSA private key
            
        Returns:
            The JWK as a dictionary
        """
        # Extract public key (only public part is needed for JWK)
        public_key = private_key.public_key()
        
        # Create JWK from public key
        jwk = JsonWebKey.import_key(public_key)
        jwk_dict = jwk.as_dict()
        
        # Add additional parameters from header
        jwk_dict.update({
            "use": "sig",
            "kid": self.HEADER["kid"],
            "alg": self.HEADER["alg"]
        })
        
        return jwk_dict
    
    def generate_jwk(self) -> Dict[str, Any]:
        """Generate JWK and save it to file.
        
        Returns:
            The JWKS as a dictionary
        """
        # Check if private key exists
        if self.private_key_path.exists():
            # Load existing private key
            with open(self.private_key_path, "rb") as f:
                private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
        else:
            # Generate new key pair
            private_key = self.generate_rsa_key_pair()
        
        # Create JWK
        jwk_dict = self.create_jwk(private_key)
        
        # Create JWKS
        jwks = {"keys": [jwk_dict]}
        
        # Save JWKS to file
        with open(self.jwk_path, "w") as f:
            json.dump(jwks, f, indent=2)
        
        return jwks