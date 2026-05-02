import logging
import random
import uuid

from django.core.cache import cache

logger = logging.getLogger(__name__)

_OTP_TTL_SECONDS = 300
_CACHE_PREFIX = "local_otp"


def send_otp(phone_number: str, recaptcha_token: str = "") -> dict:
    otp = f"{random.randint(0, 999999):06d}"
    session_info = str(uuid.uuid4())
    cache_key = f"{_CACHE_PREFIX}:{session_info}"
    phone_session_key = f"phone_session:{phone_number}"

    # Store the OTP data
    cache.set(
        cache_key,
        {
            "phone_number": phone_number,
            "otp": otp,
        },
        timeout=_OTP_TTL_SECONDS,
    )
    
    # Store phone number to session mapping for easy lookup
    cache.set(
        phone_session_key,
        session_info,
        timeout=_OTP_TTL_SECONDS,
    )

    logger.info("[LOCAL OTP] phone=%s otp=%s session=%s", phone_number, otp, session_info)
    print(f"[LOCAL OTP] phone={phone_number} otp={otp} session={session_info}", flush=True)

    return {
        "success": True,
        "session_info": session_info,
        "message": "OTP sent successfully.",
    }


def verify_otp(phone_number: str, otp: str, session_info: str) -> dict:
    cache_key = f"{_CACHE_PREFIX}:{session_info}"
    phone_session_key = f"phone_session:{phone_number}"
    payload = cache.get(cache_key)

    if not payload:
        return {"success": False, "message": "OTP expired or invalid session."}

    if payload.get("phone_number") != phone_number:
        return {"success": False, "message": "Phone number mismatch for this OTP session."}

    if payload.get("otp") != otp:
        return {"success": False, "message": "Incorrect OTP. Please try again."}

    # Clean up both cache entries
    cache.delete(cache_key)
    cache.delete(phone_session_key)

    return {
        "success": True,
        "uid": f"local-{phone_number}",
        "phone_number": phone_number,
    }