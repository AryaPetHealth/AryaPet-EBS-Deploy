import secrets

# Excludes 0/O and 1/I/L - characters that look alike when read aloud or copied off a
# printed report, which is exactly how this id gets used (front desk, phone calls).
_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
_CODE_LENGTH = 6


def generate_patient_id() -> str:
    suffix = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
    return f"ARYA-C{suffix}"
