"""
Identity Views
===============
Authentication API endpoints for the Supplica platform.

Endpoints:
    POST /api/send-otp/    — Step 1: Firebase sends OTP SMS to the phone number.
                             Returns verification_token (sessionInfo) for later use.
    POST /api/verify-otp/  — Step 2: Verify OTP + auto register or login.
    POST /api/register/    — Step 2a (legacy): Verify OTP + create new user.
    POST /api/login/       — Step 2b (legacy): Verify OTP + authenticate user.
    POST /api/admin/login/ — Email + password login for staff/superuser accounts.

Firebase OTP Flow:
    1. Frontend: Call /api/send-otp/ with { "phone_number": "+91XXXXXXXXXX",
                 "recaptcha_token": "<firebase_recaptcha_token>" }.
                 The recaptcha_token is obtained from Firebase Web SDK's
                 RecaptchaVerifier. Not needed for Firebase test phone numbers.
    2. Firebase delivers the OTP SMS to the user's phone.
    3. Backend returns { "verification_token": "<session_info>" }.
    4. User enters the OTP.
    5. Frontend: Call /api/verify-otp/ with { "phone_number", "otp",
                 "verification_token" }.
    6. Backend verifies with Firebase → creates/finds user → returns JWT tokens.
"""

import logging
import uuid
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User as AuthUser
from django.contrib.auth.models import Permission
from django.utils import timezone
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from identity.models import User, UserSession, Role
from identity.models import IncomePlusOnboardingRequest, IncomePlusOnboardingStatus
from .serializers import (
    SendOTPSerializer,
    VerifyOTPSerializer,
    PermissionSerializer,
    RoleSerializer,
    RoleWriteSerializer,
    AdminUserWriteSerializer,
    IncomePlusRequestCreateSerializer,
    IncomePlusStep1Serializer,
    IncomePlusStep2Serializer,
    IncomePlusStep3Serializer,
    IncomePlusAdminVerifySerializer,
)
from .otp_service_local import send_otp, verify_otp

logger = logging.getLogger(__name__)


def _get_auth_user_permissions(user: AuthUser) -> list[str]:
    """Return unique '<app_label>.<codename>' permission keys for the auth user."""
    perms = set()
    for perm in user.user_permissions.select_related("content_type").all():
        perms.add(f"{perm.content_type.app_label}.{perm.codename}")
    for group in user.groups.prefetch_related("permissions__content_type").all():
        for perm in group.permissions.all():
            perms.add(f"{perm.content_type.app_label}.{perm.codename}")
    return sorted(perms)


def _get_auth_user_roles(user: AuthUser) -> list[str]:
    """Return role names mapped from Django Group names."""
    return list(user.groups.values_list("name", flat=True))


# ============================================================================
# HELPER — Generate JWT token pair
# ============================================================================

def _generate_tokens(user: User) -> dict:
    """
    Generate access and refresh JWT tokens for the given user.
    Embeds public_id in the token payload (never the internal id).
    """
    refresh = RefreshToken()
    refresh["public_id"] = str(user.public_id)

    return {
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
    }


def _get_client_ip(request) -> str | None:
    """Return the real client IP, honouring X-Forwarded-For when behind a proxy."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _detect_device_type(user_agent: str) -> str:
    """Basic device-type detection from the User-Agent header."""
    ua = (user_agent or "").lower()
    if "android" in ua:
        return "mobile_android"
    if "iphone" in ua or "ipad" in ua:
        return "mobile_ios"
    return "web"


def _create_user_session(user: User, request) -> None:
    """
    Record a new active session in the identity_user_session table.
    Called after every successful login or registration.

    Fields captured from the request:
        session_token     — unique UUID string (fits CharField 255)
        device_id         — X-Device-ID header if provided by client
        device_type       — derived from User-Agent ('web' / 'mobile_android' / 'mobile_ios')
        ip_address        — real client IP (X-Forwarded-For aware)
        user_agent        — raw User-Agent header
        is_active         — True
        expires_at        — now + REFRESH_TOKEN_LIFETIME (session lives as long as refresh token)
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    refresh_lifetime = settings.SIMPLE_JWT.get("REFRESH_TOKEN_LIFETIME")

    try:
        UserSession.objects.create(
            user=user,
            session_token=str(uuid.uuid4()),
            device_id=request.META.get("HTTP_X_DEVICE_ID") or None,
            device_type=_detect_device_type(user_agent),
            ip_address=_get_client_ip(request),
            user_agent=user_agent or None,
            is_active=True,
            expires_at=timezone.now() + refresh_lifetime,
        )
    except Exception as exc:
        # Session tracking is non-critical — log the failure but never block auth
        logger.error("[SESSION] Failed to create UserSession for user %s: %s", user.public_id, exc)


# ============================================================================
# SEND OTP — POST /api/send-otp/
# ============================================================================

class SendOTPView(APIView):
    """
    Step 1 of authentication.

    Calls Firebase REST API to dispatch an OTP SMS to the given phone number.
    Returns a verification_token (Firebase sessionInfo) that must be passed
    back when verifying the OTP.

    Request body:
        {
            "phone_number": "+91XXXXXXXXXX",
            "recaptcha_token": "<firebase_web_recaptcha_token>"  // required in production
        }

    The recaptcha_token is obtained client-side from Firebase Web SDK:
        const verifier = new firebase.auth.RecaptchaVerifier('recaptcha-container');
        const token = await verifier.verify();
    For Firebase test phone numbers the recaptcha_token can be omitted.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        recaptcha_token = serializer.validated_data.get("recaptcha_token", "")

        result = send_otp(phone_number, recaptcha_token)

        if not result["success"]:
            return Response(
                {"error": result["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "OTP sent successfully.",
                "phone_number": phone_number,
                "verification_token": result["session_info"],
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# VERIFY OTP — POST /api/verify-otp/  (unified register + login)
# ============================================================================

class VerifyOTPView(APIView):
    """
    Step 2 of authentication (unified endpoint).

    Verifies the OTP via Firebase, then automatically registers the user if
    they are new or logs them in if they already have an account.

    Request body:
        {
            "phone_number": "+91XXXXXXXXXX",
            "otp": "123456",
            "verification_token": "<session_info from /api/send-otp/>"
        }

    Response:
        {
            "message": "User registered successfully." | "Login successful.",
            "is_new_user": true | false,
            "public_id": "<uuid>",
            "access_token": "<jwt>",
            "refresh_token": "<jwt>"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        otp = serializer.validated_data["otp"]
        session_info = serializer.validated_data["verification_token"]

        # Verify OTP with Firebase
        result = verify_otp(phone_number, otp, session_info)

        if not result["success"]:
            return Response(
                {"error": result["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified_phone = result["phone_number"]

        # Register or login based on whether the user already exists
        user, is_new_user = User.objects.get_or_create(phone=verified_phone)

        tokens = _generate_tokens(user)

        if is_new_user:
            logger.info("[VERIFY-OTP] New user registered: %s (public_id=%s)", verified_phone, user.public_id)
            message = "User registered successfully."
            http_status = status.HTTP_201_CREATED
        else:
            logger.info("[VERIFY-OTP] User authenticated: %s (public_id=%s)", verified_phone, user.public_id)
            _create_user_session(user, request)
            message = "Login successful."
            http_status = status.HTTP_200_OK

        return Response(
            {
                "message": message,
                "is_new_user": is_new_user,
                "public_id": str(user.public_id),
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
            },
            status=http_status,
        )


# ============================================================================
# REGISTER — POST /api/register/  (legacy: register-only endpoint)
# ============================================================================

class RegisterView(APIView):
    """
    Register a new user after Firebase OTP verification.

    Use /api/verify-otp/ for the unified register+login flow.
    This endpoint is kept for backward compatibility and returns an error
    if the phone number is already registered.

    Request body:
        {
            "phone_number": "+91XXXXXXXXXX",
            "otp": "123456",
            "verification_token": "<session_info from /api/send-otp/>"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        otp = serializer.validated_data["otp"]
        session_info = serializer.validated_data["verification_token"]

        result = verify_otp(phone_number, otp, session_info)

        if not result["success"]:
            return Response(
                {"error": result["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified_phone = result["phone_number"]

        if User.objects.filter(phone=verified_phone).exists():
            return Response(
                {"error": "Mobile number already registered. Please login instead."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            user = User.objects.create(phone=verified_phone)
        except Exception as exc:
            logger.error("[REGISTER] Failed to create user for %s: %s", verified_phone, exc)
            return Response(
                {"error": "Registration failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info("[REGISTER] New user registered: %s (public_id=%s)", verified_phone, user.public_id)

        tokens = _generate_tokens(user)

        return Response(
            {
                "message": "User registered successfully.",
                "public_id": str(user.public_id),
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
            },
            status=status.HTTP_201_CREATED,
        )


# ============================================================================
# LOGIN — POST /api/login/  (legacy: login-only endpoint)
# ============================================================================

class LoginView(APIView):
    """
    Authenticate an existing user after Firebase OTP verification.

    Use /api/verify-otp/ for the unified register+login flow.
    This endpoint is kept for backward compatibility and returns an error
    if the phone number is not yet registered.

    Request body:
        {
            "phone_number": "+91XXXXXXXXXX",
            "otp": "123456",
            "verification_token": "<session_info from /api/send-otp/>"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)

        if not serializer.is_valid():
            first_error = next(iter(serializer.errors.values()))[0]
            return Response(
                {"error": str(first_error)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        phone_number = serializer.validated_data["phone_number"]
        otp = serializer.validated_data["otp"]
        session_info = serializer.validated_data["verification_token"]

        result = verify_otp(phone_number, otp, session_info)

        if not result["success"]:
            return Response(
                {"error": result["message"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        verified_phone = result["phone_number"]

        try:
            user = User.objects.get(phone=verified_phone)
        except User.DoesNotExist:
            return Response(
                {"error": "No account found with this mobile number. Please register first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        logger.info("[LOGIN] User authenticated: %s (public_id=%s)", verified_phone, user.public_id)

        tokens = _generate_tokens(user)
        _create_user_session(user, request)

        return Response(
            {
                "message": "Login successful.",
                "public_id": str(user.public_id),
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
            },
            status=status.HTTP_200_OK,
        )


# ============================================================================
# ADMIN LOGIN — POST /api/admin/login/
# ============================================================================

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def admin_login(request):
    """
    Admin JWT Login.
    Authenticates against Django's auth_user table (staff/superuser accounts).
    Returns access and refresh tokens on success.
    Stateless — no session, no login().
    """
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response(
            {"error": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_obj = AuthUser.objects.get(email=email)
    except AuthUser.DoesNotExist:
        return Response(
            {"error": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    user = authenticate(username=user_obj.username, password=password)

    if user is None or not user.is_active:
        return Response(
            {"error": "Invalid credentials."},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not (user.is_staff or user.is_superuser):
        return Response(
            {"error": "Access denied. Admin account required."},
            status=status.HTTP_403_FORBIDDEN,
        )

    refresh = RefreshToken.for_user(user)

    logger.info("[ADMIN LOGIN] Admin authenticated: %s", user.email)

    return Response(
        {
            "message": "Login successful.",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "is_superuser": user.is_superuser,
                "roles": _get_auth_user_roles(user),
                "permissions": _get_auth_user_permissions(user),
            },
        },
        status=status.HTTP_200_OK,
    )


class AdminMePermissionsView(APIView):
    """Return current authenticated admin user's role and permission payload."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not (user.is_staff or user.is_superuser):
            return _api_response(
                {"error": "Access denied. Admin account required."},
                code=403,
                message="Forbidden",
                http_status=403,
            )
        return _api_response(
            {
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "is_superuser": user.is_superuser,
                    "roles": _get_auth_user_roles(user),
                    "permissions": _get_auth_user_permissions(user),
                }
            }
        )


# ============================================================================
# HELPER — Wrap API response in standard envelope
# ============================================================================

def _api_response(data=None, code=200, message="Success", http_status=None):
    """Return a consistent { code, message, data } envelope."""
    return Response(
        {"code": code, "message": message, "data": data or {}},
        status=http_status or code,
    )


def _sync_role_to_group(role: Role) -> Group:
    """
    Ensure a Django Group mirrors the given Role.
    Creates the Group if it doesn't exist yet, then syncs permissions.
    """
    group, _ = Group.objects.get_or_create(name=role.name)
    group.permissions.set(role.permissions.all())
    return group


def _deny_if_no_perm(request, perm_codename: str, error_message: str = "Permission denied."):
    """Return a 403 envelope when the current user lacks the required Django permission."""
    if not request.user.has_perm(perm_codename):
        return _api_response({"error": error_message}, code=403, message="Forbidden", http_status=403)
    return None


# ============================================================================
# ROLE CRUD — /api_roles/
# ============================================================================

class RoleListView(APIView):
    """GET /api_roles/ — list all roles with permissions."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        deny = _deny_if_no_perm(request, "identity.view_role", "You do not have permission to view roles.")
        if deny:
            return deny
        roles = Role.objects.prefetch_related('permissions__content_type').all()
        data = []
        for role in roles:
            data.append({
                "id": role.id,
                "name": role.name,
                "description": role.description,
                "permissions": PermissionSerializer(role.permissions.all(), many=True).data,
            })
        return _api_response({"roles": data})


class RoleCreateView(APIView):
    """POST /api_roles/create/ — create a new role."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        deny = _deny_if_no_perm(request, "identity.add_role", "You do not have permission to add roles.")
        if deny:
            return deny
        ser = RoleWriteSerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        name = ser.validated_data["name"]
        if Role.objects.filter(name__iexact=name).exists():
            return _api_response({"error": f"Role '{name}' already exists."}, code=400, message="Duplicate", http_status=400)

        role = Role.objects.create(
            name=name,
            description=ser.validated_data.get("description", ""),
        )
        perm_ids = ser.validated_data.get("permissions", [])
        if perm_ids:
            role.permissions.set(Permission.objects.filter(id__in=perm_ids))

        _sync_role_to_group(role)
        logger.info("[ROLE] Created role '%s' (id=%d)", role.name, role.id)
        return _api_response(
            {"role": RoleSerializer(role).data},
            code=201,
            message="Role created",
            http_status=201,
        )


class RoleUpdateView(APIView):
    """PUT /api_roles/<id>/update/ — update a role's name, description, permissions."""
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        deny = _deny_if_no_perm(request, "identity.change_role", "You do not have permission to update roles.")
        if deny:
            return deny
        try:
            role = Role.objects.get(pk=pk)
        except Role.DoesNotExist:
            return _api_response({"error": "Role not found."}, code=404, message="Not found", http_status=404)

        ser = RoleWriteSerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        new_name = ser.validated_data["name"]
        if Role.objects.filter(name__iexact=new_name).exclude(pk=pk).exists():
            return _api_response({"error": f"Role '{new_name}' already exists."}, code=400, message="Duplicate", http_status=400)

        # Rename the synced Django Group if the name changed
        old_name = role.name
        role.name = new_name
        role.description = ser.validated_data.get("description", role.description)
        role.save()

        perm_ids = ser.validated_data.get("permissions", [])
        role.permissions.set(Permission.objects.filter(id__in=perm_ids))

        # Sync group (handle rename)
        if old_name != new_name:
            Group.objects.filter(name=old_name).update(name=new_name)
        _sync_role_to_group(role)

        logger.info("[ROLE] Updated role '%s' (id=%d)", role.name, role.id)
        return _api_response({"role": RoleSerializer(role).data}, message="Role updated")


class RoleDeleteView(APIView):
    """DELETE /api_roles/<id>/delete/ — delete a role and its synced Group."""
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        deny = _deny_if_no_perm(request, "identity.delete_role", "You do not have permission to delete roles.")
        if deny:
            return deny
        try:
            role = Role.objects.get(pk=pk)
        except Role.DoesNotExist:
            return _api_response({"error": "Role not found."}, code=404, message="Not found", http_status=404)

        name = role.name
        Group.objects.filter(name=name).delete()
        role.delete()
        logger.info("[ROLE] Deleted role '%s'", name)
        return _api_response(message=f"Role '{name}' deleted")


# ============================================================================
# PERMISSIONS LIST — /api_permissions/
# ============================================================================

class PermissionListView(APIView):
    """GET /api_permissions/ — list all Django auth permissions."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        deny = _deny_if_no_perm(request, "auth.view_permission", "You do not have permission to view permissions.")
        if deny:
            return deny
        perms = Permission.objects.select_related('content_type').all().order_by(
            'content_type__app_label', 'codename'
        )
        return _api_response({"permissions": PermissionSerializer(perms, many=True).data})


# ============================================================================
# ADMIN USER CRUD — /api_users/
# ============================================================================

class AdminUserListView(APIView):
    """GET /api_users/ — list Django auth_user records with their roles."""
    permission_classes = [IsAdminUser]

    def get(self, request):
        deny = _deny_if_no_perm(request, "auth.view_user", "You do not have permission to view users.")
        if deny:
            return deny
        auth_users = AuthUser.objects.prefetch_related('groups').all()
        auth_list = []
        for u in auth_users:
            # Map Django Groups back to Role IDs for the frontend dropdown
            group_names = list(u.groups.values_list('name', flat=True))
            roles_qs = Role.objects.filter(name__in=group_names)
            groups_data = [{"id": r.id, "name": r.name} for r in roles_qs]

            auth_list.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_staff": u.is_staff,
                "is_active": u.is_active,
                "is_superuser": u.is_superuser,
                "date_joined": u.date_joined.isoformat(),
                "groups": groups_data,
            })

        return _api_response({"users": auth_list})


class AdminUserCreateView(APIView):
    """POST /api_users/create/ — create a new Django auth_user."""
    permission_classes = [IsAdminUser]

    def post(self, request):
        deny = _deny_if_no_perm(request, "auth.add_user", "You do not have permission to add users.")
        if deny:
            return deny
        ser = AdminUserWriteSerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        if AuthUser.objects.filter(username=d["username"]).exists():
            return _api_response({"error": f"Username '{d['username']}' already taken."}, code=400, message="Duplicate", http_status=400)

        if not d.get("password"):
            return _api_response({"error": "Password is required for new users."}, code=400, message="Validation failed", http_status=400)

        user = AuthUser.objects.create_user(
            username=d["username"],
            email=d.get("email", ""),
            password=d["password"],
            first_name=d.get("first_name", ""),
            last_name=d.get("last_name", ""),
            is_staff=d.get("is_staff", False),
        )

        # Assign role-synced groups
        role_ids = d.get("groups", [])
        if role_ids:
            role_names = list(Role.objects.filter(id__in=role_ids).values_list('name', flat=True))
            groups = Group.objects.filter(name__in=role_names)
            user.groups.set(groups)

        logger.info("[USER] Created auth_user '%s' (id=%d)", user.username, user.id)
        return _api_response(
            {"user": {"id": user.id, "username": user.username}},
            code=201,
            message="User created",
            http_status=201,
        )


class AdminUserUpdateView(APIView):
    """PUT /api_users/<id>/update/ — update an existing auth_user."""
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        deny = _deny_if_no_perm(request, "auth.change_user", "You do not have permission to update users.")
        if deny:
            return deny
        try:
            user = AuthUser.objects.get(pk=pk)
        except AuthUser.DoesNotExist:
            return _api_response({"error": "User not found."}, code=404, message="Not found", http_status=404)

        ser = AdminUserWriteSerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data

        # Check username uniqueness (exclude self)
        if AuthUser.objects.filter(username=d["username"]).exclude(pk=pk).exists():
            return _api_response({"error": f"Username '{d['username']}' already taken."}, code=400, message="Duplicate", http_status=400)

        user.username = d["username"]
        user.email = d.get("email", user.email)
        user.first_name = d.get("first_name", user.first_name)
        user.last_name = d.get("last_name", user.last_name)
        user.is_staff = d.get("is_staff", user.is_staff)
        user.is_active = d.get("is_active", user.is_active)

        if d.get("password"):
            user.set_password(d["password"])

        user.save()

        # Assign role-synced groups
        role_ids = d.get("groups", [])
        role_names = list(Role.objects.filter(id__in=role_ids).values_list('name', flat=True))
        groups = Group.objects.filter(name__in=role_names)
        user.groups.set(groups)

        logger.info("[USER] Updated auth_user '%s' (id=%d)", user.username, user.id)
        return _api_response({"user": {"id": user.id, "username": user.username}}, message="User updated")


class AdminUserDeleteView(APIView):
    """DELETE /api_users/<id>/delete/ — delete an auth_user."""
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        deny = _deny_if_no_perm(request, "auth.delete_user", "You do not have permission to delete users.")
        if deny:
            return deny
        try:
            user = AuthUser.objects.get(pk=pk)
        except AuthUser.DoesNotExist:
            return _api_response({"error": "User not found."}, code=404, message="Not found", http_status=404)

        username = user.username
        user.delete()
        logger.info("[USER] Deleted auth_user '%s'", username)
        return _api_response(message=f"User '{username}' deleted")


def _incomeplus_payload(obj: IncomePlusOnboardingRequest):
    return {
        "public_id": str(obj.public_id),
        "full_name": obj.full_name,
        "email": obj.email,
        "phone": obj.phone,
        "company_name": obj.company_name,
        "designation": obj.designation,
        "current_step": obj.current_step,
        "status": obj.status,
        "step1_completed": obj.step1_completed,
        "step2_completed": obj.step2_completed,
        "step3_completed": obj.step3_completed,
        "admin_notes": obj.admin_notes,
        "submitted_at": obj.submitted_at,
        "linked_admin_user_id": obj.linked_admin_user_id,
    }


def _incomeplus_find_by_token(token_value):
    try:
        return IncomePlusOnboardingRequest.objects.get(invite_token=token_value)
    except IncomePlusOnboardingRequest.DoesNotExist:
        return None


class IncomePlusRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = IncomePlusRequestCreateSerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        req, created = IncomePlusOnboardingRequest.objects.update_or_create(
            email=d["email"],
            defaults={
                "full_name": d["full_name"],
                "phone": d["phone"],
                "company_name": d.get("company_name") or None,
                "status": IncomePlusOnboardingStatus.REQUESTED,
                "current_step": 1,
            },
        )
        code = 201 if created else 200
        return _api_response({"request": _incomeplus_payload(req)}, code=code, message="Onboarding request saved", http_status=code)


class IncomePlusSendInviteView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        deny = _deny_if_no_perm(request, "identity.change_incomeplusonboardingrequest", "You do not have permission to send invite links.")
        if deny:
            return deny

        try:
            req = IncomePlusOnboardingRequest.objects.get(pk=pk)
        except IncomePlusOnboardingRequest.DoesNotExist:
            return _api_response({"error": "Onboarding request not found."}, code=404, message="Not found", http_status=404)

        req.invite_token = uuid.uuid4()
        req.token_expires_at = timezone.now() + timedelta(days=2)
        req.invite_sent_at = timezone.now()
        req.status = IncomePlusOnboardingStatus.INVITED
        req.save(update_fields=["invite_token", "token_expires_at", "invite_sent_at", "status", "updated_at"])

        frontend_url = request.query_params.get("frontend_url") or "http://localhost:5174"
        registration_link = f"{frontend_url.rstrip('/')}/incomeplus/onboarding?token={req.invite_token}"

        return _api_response({"request": _incomeplus_payload(req), "registration_link": registration_link}, message="Invite link generated")


class IncomePlusValidateTokenView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        if not token:
            return _api_response({"error": "Token is required."}, code=400, message="Validation failed", http_status=400)

        req = _incomeplus_find_by_token(token)
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        if req.token_expires_at and req.token_expires_at < timezone.now():
            return _api_response({"error": "Onboarding token has expired."}, code=400, message="Expired token", http_status=400)

        return _api_response({"request": _incomeplus_payload(req)})


class IncomePlusOnboardingStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        if not token:
            return _api_response({"error": "Token is required."}, code=400, message="Validation failed", http_status=400)

        req = _incomeplus_find_by_token(token)
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        return _api_response({"request": _incomeplus_payload(req)})


class IncomePlusStep1View(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = IncomePlusStep1Serializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        req = _incomeplus_find_by_token(d["token"])
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        req.full_name = d["full_name"]
        req.email = d["email"]
        req.phone = d["phone"]
        req.company_name = d.get("company_name") or None
        req.designation = d.get("designation") or None
        req.step1_completed = True
        req.current_step = 2
        req.status = IncomePlusOnboardingStatus.IN_PROGRESS

        auth_user, _ = AuthUser.objects.get_or_create(
            email=d["email"],
            defaults={
                "username": d["email"],
                "first_name": d["full_name"].split(" ")[0],
                "last_name": " ".join(d["full_name"].split(" ")[1:]),
                "is_active": True,
                "is_staff": False,
            },
        )
        auth_user.username = d["email"]
        auth_user.email = d["email"]
        auth_user.first_name = d["full_name"].split(" ")[0]
        auth_user.last_name = " ".join(d["full_name"].split(" ")[1:])
        auth_user.is_active = True
        auth_user.set_password(d["password"])
        auth_user.save()

        req.linked_admin_user = auth_user
        req.save()

        return _api_response({"request": _incomeplus_payload(req)}, message="Step 1 saved")


class IncomePlusStep2View(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        req = _incomeplus_find_by_token(token)
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        return _api_response(
            {
                "bank_details": {
                    "bank_account_holder": req.bank_account_holder,
                    "bank_name": req.bank_name,
                    "bank_account_number": req.bank_account_number,
                    "bank_ifsc": req.bank_ifsc,
                    "bank_branch": req.bank_branch,
                    "upi_id": req.upi_id,
                }
            }
        )

    def post(self, request):
        ser = IncomePlusStep2Serializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        req = _incomeplus_find_by_token(d["token"])
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        req.bank_account_holder = d["bank_account_holder"]
        req.bank_name = d["bank_name"]
        req.bank_account_number = d["bank_account_number"]
        req.bank_ifsc = d["bank_ifsc"]
        req.bank_branch = d.get("bank_branch") or None
        req.upi_id = d.get("upi_id") or None
        req.step2_completed = True
        req.current_step = 3
        req.status = IncomePlusOnboardingStatus.IN_PROGRESS
        req.save()

        return _api_response({"request": _incomeplus_payload(req)}, message="Step 2 saved")


class IncomePlusStep3View(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        token = request.query_params.get("token")
        req = _incomeplus_find_by_token(token)
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        return _api_response(
            {
                "kyc_details": {
                    "pan_number": req.pan_number,
                    "gst_number": req.gst_number,
                    "aadhar_number": req.aadhar_number,
                    "pan_document_url": req.pan_document_url,
                    "gst_document_url": req.gst_document_url,
                    "aadhar_document_url": req.aadhar_document_url,
                }
            }
        )

    def post(self, request):
        ser = IncomePlusStep3Serializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        req = _incomeplus_find_by_token(d["token"])
        if not req:
            return _api_response({"error": "Invalid onboarding token."}, code=404, message="Not found", http_status=404)

        req.pan_number = d["pan_number"]
        req.gst_number = d.get("gst_number") or None
        req.aadhar_number = d.get("aadhar_number") or None
        req.pan_document_url = d.get("pan_document_url") or None
        req.gst_document_url = d.get("gst_document_url") or None
        req.aadhar_document_url = d.get("aadhar_document_url") or None
        req.step3_completed = True
        req.current_step = 3
        req.status = IncomePlusOnboardingStatus.PENDING_APPROVAL
        req.submitted_at = timezone.now()
        req.save()

        return _api_response({"request": _incomeplus_payload(req)}, message="KYC submitted. Admin will review within 24 hours.")


class IncomePlusAdminRequestsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        deny = _deny_if_no_perm(request, "identity.view_incomeplusonboardingrequest", "You do not have permission to view onboarding requests.")
        if deny:
            return deny

        status_filter = request.query_params.get("status", "")
        qs = IncomePlusOnboardingRequest.objects.all().order_by("-created_at")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return _api_response({"requests": [_incomeplus_payload(obj) for obj in qs]})


class IncomePlusAdminVerifyView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, public_id):
        deny = _deny_if_no_perm(request, "identity.change_incomeplusonboardingrequest", "You do not have permission to verify onboarding requests.")
        if deny:
            return deny

        try:
            req = IncomePlusOnboardingRequest.objects.get(public_id=public_id)
        except IncomePlusOnboardingRequest.DoesNotExist:
            return _api_response({"error": "Onboarding request not found."}, code=404, message="Not found", http_status=404)

        ser = IncomePlusAdminVerifySerializer(data=request.data)
        if not ser.is_valid():
            return _api_response({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        action = ser.validated_data["action"]
        req.admin_notes = ser.validated_data.get("admin_notes") or None

        if action == "approve":
            req.status = IncomePlusOnboardingStatus.APPROVED
            if req.linked_admin_user_id:
                req.linked_admin_user.is_staff = True
                req.linked_admin_user.is_active = True
                req.linked_admin_user.save(update_fields=["is_staff", "is_active"])
        else:
            req.status = IncomePlusOnboardingStatus.REJECTED

        req.save(update_fields=["status", "admin_notes", "updated_at"])
        return _api_response({"request": _incomeplus_payload(req)}, message=f"Request {action}d")
