import os
import socket
import json

# pip install cryptography
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend

# Voters register to vote prior to receiving a token.
# Here we assume that each client would have a secure and private voter_id, or other forms of identification
valid_voter_ids = {"voter_1", "voter_2", "voter_3", "voter_4"}
token_distributed_ids = set()

class ElectionAuthorityServer:
    def __init__(self, host='127.0.0.1', port=5000, key_file="ea_private_key.pem"):
        """
        Constructor for the ElectionAuthorityServer class.
        Will create a file to store the private key on the first time it is run. 
        Will then print the public key, which should be hardcoded into any file that needs it.
        On future runs it will load the previously used private key.

        Parameters:
            host : str
                The IP address of the election authority.
            port : int
                The port the election authority is listening on.
            key_file : str
                The file to load the private key from, or store into.
        """
        self.key_file = key_file
        
        # Load the previous key if it has already been created
        if os.path.exists(self.key_file):
            # Load existing key
            print(f"[*] Loading existing EA key from {self.key_file}...")
            with open(self.key_file, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None, # TODO: Encrypt the stored key and use password
                    backend=default_backend()
                )
        else:
            # Generate and save new key
            print("[*] No key found. Generating new EA master key...")
            self.private_key = rsa.generate_private_key(
                public_exponent=65537, key_size=2048, backend=default_backend()
            )
            # Save it so we can reuse it next time
            with open(self.key_file, "wb") as f:
                f.write(self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
        
        self.public_key = self.private_key.public_key()
        self.display_public_key()
        
        # Setup Socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((host, port))
        self.server_socket.listen(5)
        print(f"[*] EA Server listening on {host}:{port}")
    
    def display_public_key(self):
        """
        Prints the Public Key so you can copy-paste it into your other scripts.
        """
        pub_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        print("\n--- COPY THIS PUBLIC KEY INTO YOUR NODE/CLIENT SCRIPTS ---")
        print(pub_bytes.decode('utf-8'))
        print("-----------------------------------------------------------\n")

    def run(self):
        """
        Run the election authority server. Will take requests to sign tokens from registered voters.
        """
        while True:
            client, addr = self.server_socket.accept()
            data = client.recv(4096).decode('utf-8')
            if not data: continue
            
            request = None
            try:
                request = json.loads(data)
            except json.decoder.JSONDecodeError as e:
                print(f"Bad JSON: {data}")
                client.close()
                continue
            if not isinstance(request, dict):
                client.close()
                continue
            
            if not ("voter_id" in request and "token" in request):
                print(f"Bad JSON: {request}")
                client.close()
                continue

            voter_id = request['voter_id']
            token_bytes = request['token'].encode('utf-8')
            
            print(f"Received request from {voter_id}")

            if not voter_id in valid_voter_ids:
                print(f"{voter_id} is not a registered voter.")
                client.close()
                continue
            
            if voter_id in token_distributed_ids:
                print(f"{voter_id} already obtained a token.")
                client.close()
                continue
            
            token_distributed_ids.add(voter_id)

            # Sign the token
            signature = self.private_key.sign(
                token_bytes,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256()
            )

            print(f"Signed token for {voter_id}")

            # Send signature back in hex format
            client.send(signature.hex().encode('utf-8'))
            client.close()

if __name__ == "__main__":
    EA = ElectionAuthorityServer()
    EA.run()