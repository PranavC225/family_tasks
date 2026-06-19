import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


priv = ec.generate_private_key(ec.SECP256R1())
pem = priv.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
pub_point = priv.public_key().public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint,
)
print("VAPID_PRIVATE_KEY=" + base64.b64encode(pem).decode())
print("VAPID_PUBLIC_KEY=" + b64u(pub_point))
print("VAPID_SUBJECT=mailto:pranav.chandode@gmail.com")
