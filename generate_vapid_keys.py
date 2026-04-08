#!/usr/bin/env python3
"""Generera VAPID-nycklar för web push-notifikationer.

Kör: python3 generate_vapid_keys.py
Lägg sedan till output-värdena som miljövariabler i Render.
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)


def generate_vapid_keys():
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())

    # Private key — base64url-kodad DER
    priv_der = key.private_bytes(Encoding.DER, PrivateFormat.PKCS8, NoEncryption())
    private_key = base64.urlsafe_b64encode(priv_der).decode().rstrip("=")

    # Public key — uncompressed EC point (65 bytes), base64url-kodad
    pub_der = key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    public_key = base64.urlsafe_b64encode(pub_der).decode().rstrip("=")

    return private_key, public_key


if __name__ == "__main__":
    priv, pub = generate_vapid_keys()
    print("Lägg till dessa i Render som Environment Variables:\n")
    print(f"VAPID_PRIVATE_KEY={priv}")
    print(f"VAPID_PUBLIC_KEY={pub}")
    print(f"VAPID_SUBJECT=mailto:kontakt@spelningskollen.se")
    print()
    print("Och i Next.js (.env.local / Render):")
    print(f"NEXT_PUBLIC_VAPID_PUBLIC_KEY={pub}")
