import os
import hashlib
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

class CryptoManager:
    def __init__(self, key_dir="data/keys"):
        self.key_dir = key_dir
        os.makedirs(self.key_dir, exist_ok=True)
        self.private_key_path = os.path.join(self.key_dir, "private.pem")
        self.public_key_path = os.path.join(self.key_dir, "public.pem")
        self.private_key = None
        self.public_key = None
        self._load_or_generate_keys()

    def _load_or_generate_keys(self):
        if os.path.exists(self.private_key_path) and os.path.exists(self.public_key_path):
            with open(self.private_key_path, "rb") as f:
                self.private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
            with open(self.public_key_path, "rb") as f:
                self.public_key = serialization.load_pem_public_key(f.read(), backend=default_backend())
        else:
            self._generate_new_keys()

    def _generate_new_keys(self):
        self.private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096,
            backend=default_backend()
        )
        self.public_key = self.private_key.public_key()
        with open(self.private_key_path, "wb") as f:
            f.write(self.private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        with open(self.public_key_path, "wb") as f:
            f.write(self.public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

    def get_public_key_pem(self):
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode("utf-8")

    def get_key_fingerprint(self):
        pem_data = self.get_public_key_pem().encode()
        return hashlib.sha256(pem_data).hexdigest()

    def encrypt_message(self, message: str, recipient_public_key_pem: str) -> str:
        recipient_key = serialization.load_pem_public_key(
            recipient_public_key_pem.encode(), backend=default_backend()
        )
        aes_key = os.urandom(32)
        nonce = os.urandom(12)
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(message.encode()) + encryptor.finalize()
        encrypted_aes_key = recipient_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        combined = base64.b64encode(encrypted_aes_key + b"|" + nonce + b"|" + encryptor.tag + b"|" + ciphertext).decode()
        return combined

    def decrypt_message(self, encrypted_data: str) -> str:
        parts = base64.b64decode(encrypted_data.encode()).split(b"|")
        encrypted_aes_key, nonce, tag, ciphertext = parts[0], parts[1], parts[2], parts[3]
        aes_key = self.private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        cipher = Cipher(algorithms.AES(aes_key), modes.GCM(nonce, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return (decryptor.update(ciphertext) + decryptor.finalize()).decode("utf-8")

    @staticmethod
    def sha256_hash(data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()

    def export_public_key_text(self):
        return self.get_public_key_pem()

    def import_public_key_text(self, pem_text: str):
        return serialization.load_pem_public_key(pem_text.encode(), backend=default_backend())