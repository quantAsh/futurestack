import pyotp
import qrcode
import io
import base64

def generate_mfa_secret() -> str:
    """Generate a random secret for TOTP MFA."""
    return pyotp.random_base32()

def get_totp_uri(secret: str, user_email: str, issuer_name: str = "NomadNestAI") -> str:
    """Get the provisioning URI for the authenticator app."""
    return pyotp.totp.TOTP(secret).provisioning_uri(name=user_email, issuer_name=issuer_name)

def generate_qr_code(uri: str) -> str:
    """Generate a QR code image as a base64 string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def verify_totp(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code)


# --- Recovery Codes ---
import secrets
import hashlib
import hmac

def generate_recovery_codes(count: int = 8, length: int = 12) -> list[str]:
    """
    Generate a set of one-time recovery codes.
    Returns plain codes (to display to user) - caller should hash before storing.
    """
    codes = []
    for _ in range(count):
        # Generate random alphanumeric code (uppercase for readability)
        code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(length))
        # Format as XXXX-XXXX-XXXX for readability
        formatted = '-'.join([code[i:i+4] for i in range(0, len(code), 4)])
        codes.append(formatted)
    return codes


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for secure storage."""
    # Remove dashes and lowercase for consistent hashing
    normalized = code.replace('-', '').upper()
    return hashlib.sha256(normalized.encode()).hexdigest()


def verify_recovery_code(input_code: str, hashed_codes: list[str]) -> int | None:
    """
    Verify a recovery code against a list of hashed codes.
    Returns the index of the matching code (for removal), or None if no match.
    Uses constant-time comparison to prevent timing attacks.
    """
    normalized = input_code.replace('-', '').upper()
    input_hash = hashlib.sha256(normalized.encode()).hexdigest()
    
    for i, stored_hash in enumerate(hashed_codes):
        if hmac.compare_digest(input_hash, stored_hash):
            return i
    return None

