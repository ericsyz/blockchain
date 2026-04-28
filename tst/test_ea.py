import socket
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

# Hardcoded EA Public Key
# Hardcode the key after running election_authority.py for the first time
EA_PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
...
-----END PUBLIC KEY-----"""

ea_public_key = serialization.load_pem_public_key(
    EA_PUBLIC_KEY_PEM.encode('utf-8'),
    backend=default_backend()
)

def verify_token(public_key, token, signature_hex):
    signature_bytes = bytes.fromhex(signature_hex)
    token_bytes = token.encode('utf-8')
    
    try:
        public_key.verify(
            signature_bytes,
            token_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return True
    except InvalidSignature:
        return False

def request_signature(voter_id, token):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(5)
    client.connect(('127.0.0.1', 5000))
    
    request = {"voter_id": voter_id, "token": token}
    client.send(json.dumps(request).encode('utf-8'))
    
    try:
        signature_hex = client.recv(4096).decode('utf-8')
        client.close()
        return signature_hex
    except socket.timeout:
        client.close()
        return None

class BlockchainTests(unittest.TestCase):
    def test_receive_signed_token(self):
        token_1 = "SECRET_TOKEN_1"
        signature_1 = request_signature("voter_1", token_1)
        self.assertTrue(signature_1 != None)
        self.assertTrue(verify_token(ea_public_key, token_1, signature_1))
    
    def test_token_not_validated_by_wrong_signature(self):
        token_1 = "SECRET_TOKEN_1"
        token_2 = "SECRET_TOKEN_2"
        signature_2 = request_signature("voter_2", token_2)
        self.assertFalse(verify_token(ea_public_key, token_1, signature_2))
    
    def test_single_token_per_voter(self):
        token_3 = "SECRET_TOKEN_3"
        signature_3 = request_signature("voter_3", token_3)
        self.assertTrue(signature_3 != None)

        signature_3_b = request_signature("voter_3", token_3)
        self.assertTrue(signature_3_b == None)

    

if __name__ == "__main__":
    unittest.main()