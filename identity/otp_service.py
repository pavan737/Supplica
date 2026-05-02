"""
OTP Service — Firebase Phone Authentication
=============================================
All OTP sending and verification is handled exclusively by Firebase.

Firebase REST Identity Toolkit API:
  - sendVerificationCode  : Firebase sends OTP SMS to the user's phone.
  - signInWithPhoneNumber : Verify OTP + sessionInfo → Firebase ID token.
Firebase Admin SDK verifies the returned ID token server-side.

Requirements:
  - Firebase project on the Blaze (pay-as-you-go) plan for SMS delivery.
  - Frontend must supply recaptcha_token via Firebase Web SDK RecaptchaVerifier.
    (Not needed for Firebase test phone numbers added in Firebase Console.)
"""

import logging
from pathlib import Path

import requests
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from decouple import config

logger = logging.getLogger(__name__)

# ============================================================================
# FIREBASE INITIALIZATION (Admin SDK always initialised — used in production)
# ============================================================================

_CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "firebase-credentials.json"

if not firebase_admin._apps:
    _cred = credentials.Certificate(str(_CREDENTIALS_PATH))
    firebase_admin.initialize_app(_cred)
    logger.info("[FIREBASE] Firebase Admin SDK initialized.")

FIREBASE_WEB_API_KEY = config("FIREBASE_WEB_API_KEY")

_SEND_OTP_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:sendVerificationCode"
    f"?key={FIREBASE_WEB_API_KEY}"
)
_VERIFY_OTP_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPhoneNumber"
    f"?key={FIREBASE_WEB_API_KEY}"
)

# ============================================================================
# PUBLIC API
# ============================================================================

def send_otp(phone_number: str, recaptcha_token: str = "") -> dict:
    """
    Trigger Firebase to send an OTP SMS to the given phone number.

    Args:
        phone_number:    Phone number in E.164 format (e.g. +91XXXXXXXXXX).
        recaptcha_token: reCAPTCHA token from Firebase Web SDK RecaptchaVerifier.
                         Required for production. Not needed for Firebase test
                         phone numbers added in Firebase Console.

    Returns:
        On success: {"success": True, "session_info": "...", "message": "..."}
        On failure: {"success": False, "message": "..."}
    """
    return _send_otp_firebase(phone_number, recaptcha_token)


def verify_otp(phone_number: str, otp: str, session_info: str) -> dict:
    """
    Verify the OTP entered by the user via Firebase.

    Args:
        phone_number:  Phone number in E.164 format.
        otp:           6-digit OTP entered by the user.
        session_info:  The session_info token returned by send_otp().

    Returns:
        On success: {"success": True, "uid": "...", "phone_number": "..."}
        On failure: {"success": False, "message": "..."}
    """
    return _verify_otp_firebase(phone_number, otp, session_info)


# ============================================================================
# FIREBASE IMPLEMENTATION
# ============================================================================

def _send_otp_firebase(phone_number: str, recaptcha_token: str) -> dict:
    """Call Firebase REST API to dispatch an OTP SMS."""
    payload = {"phoneNumber": phone_number}
    if recaptcha_token:
        payload["recaptchaToken"] = recaptcha_token

    try:
        response = requests.post(_SEND_OTP_URL, json=payload, timeout=10)
        data = response.json()
    except requests.RequestException as exc:
        logger.error("[FIREBASE] Network error in sendVerificationCode for %s: %s", phone_number, exc)
        return {"success": False, "message": "Network error while contacting Firebase."}

    if not response.ok:
        error_code = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        logger.error("[FIREBASE] sendVerificationCode failed for %s: %s", phone_number, error_code)
        return {"success": False, "message": _map_firebase_error(error_code)}

    session_info = data.get("sessionInfo")
    if not session_info:
        logger.error("[FIREBASE] Missing sessionInfo in response for %s", phone_number)
        return {"success": False, "message": "Unexpected response from Firebase. Please try again."}

    logger.info("[FIREBASE] OTP dispatched via Firebase for %s", phone_number)
    return {
        "success": True,
        "session_info": session_info,
        "message": "OTP sent successfully.",
    }


def _verify_otp_firebase(phone_number: str, otp: str, session_info: str) -> dict:
    """Verify OTP with Firebase and validate the returned ID token."""
    payload = {
        "phoneNumber": phone_number,
        "code": otp,
        "sessionInfo": session_info,
    }

    try:
        response = requests.post(_VERIFY_OTP_URL, json=payload, timeout=10)
        data = response.json()
    except requests.RequestException as exc:
        logger.error("[FIREBASE] Network error in signInWithPhoneNumber for %s: %s", phone_number, exc)
        return {"success": False, "message": "Network error while contacting Firebase."}

    if not response.ok:
        error_code = data.get("error", {}).get("message", "UNKNOWN_ERROR")
        logger.error("[FIREBASE] signInWithPhoneNumber failed for %s: %s", phone_number, error_code)
        return {"success": False, "message": _map_firebase_error(error_code)}

    id_token = data.get("idToken")
    if not id_token:
        logger.error("[FIREBASE] Missing idToken in response for %s", phone_number)
        return {"success": False, "message": "Unexpected response from Firebase. Please try again."}

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
    except firebase_auth.ExpiredIdTokenError:
        logger.error("[FIREBASE] ID token expired for %s", phone_number)
        return {"success": False, "message": "Firebase token expired. Please request a new OTP."}
    except Exception as exc:
        logger.error("[FIREBASE] ID token verification failed for %s: %s", phone_number, exc)
        return {"success": False, "message": "Failed to verify authentication token."}

    uid = decoded_token.get("uid")
    verified_phone = decoded_token.get("phone_number", phone_number)

    logger.info("[FIREBASE] OTP verified for %s (uid=%s)", verified_phone, uid)
    return {
        "success": True,
        "uid": uid,
        "phone_number": verified_phone,
    }


# ============================================================================
# FIREBASE ERROR MAPPER
# ============================================================================

def _map_firebase_error(firebase_error_code: str) -> str:
    """Translate raw Firebase REST API error codes to user-friendly messages."""
    error_map = {
        "BILLING_NOT_ENABLED": (
            "Firebase Phone Auth requires the Blaze (pay-as-you-go) plan. "
            "Upgrade at console.firebase.google.com, or use DEBUG=True to test locally without billing."
        ),
        "INVALID_PHONE_NUMBER": (
            "Invalid phone number. Please use international format (+91XXXXXXXXXX)."
        ),
        "TOO_MANY_ATTEMPTS_TRY_LATER": (
            "Too many OTP requests. Please wait a few minutes and try again."
        ),
        "QUOTA_EXCEEDED": "SMS quota exceeded. Please try again later.",
        "INVALID_CODE": "Incorrect OTP. Please check the code and try again.",
        "CODE_EXPIRED": "OTP has expired. Please request a new one.",
        "SESSION_EXPIRED": "Verification session has expired. Please request a new OTP.",
        "INVALID_SESSION_INFO": (
            "Invalid or expired verification session. Please request a new OTP."
        ),
        "MISSING_CLIENT_TYPE": (
            "reCAPTCHA token required. The frontend must provide 'recaptcha_token' "
            "obtained from Firebase Web SDK's RecaptchaVerifier."
        ),
        "MISSING_CLIENT_IDENTIFIER": (
            "reCAPTCHA token required. The frontend must provide 'recaptcha_token' "
            "obtained from Firebase Web SDK's RecaptchaVerifier."
        ),
        "CAPTCHA_CHECK_FAILED": "reCAPTCHA verification failed. Please retry.",
        "USER_DISABLED": "This phone number has been disabled. Please contact support.",
        "OPERATION_NOT_ALLOWED": (
            "Phone authentication is not enabled for this Firebase project."
        ),
    }
    for code, message in error_map.items():
        if code in firebase_error_code:
            return message
    return f"Authentication error: {firebase_error_code}"
