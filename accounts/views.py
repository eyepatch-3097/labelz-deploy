from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from .forms import LoginForm, SignupStep1Form, SignupOrgForm
from .models import Org, User, OrgJoinRequest
from .utils import split_email_domain, is_generic_email_domain
from django.db import transaction
from django.core.mail import send_mail
from django.utils import timezone
from .models import EmailOTP

class LabelcraftLoginView(LoginView):
    authentication_form = LoginForm
    template_name = 'accounts/login.html'


def logout_view(request):
    logout(request)
    return redirect('login')


@require_http_methods(["GET", "POST"])
def signup_step1(request):
    """
    Step 1: email + password only.
    Logic:
    - If company domain & org exists -> create pending user + join request + show pending msg
    - Else (generic OR first company user) -> stash email+password in session -> redirect to signup_org
    """
    if request.method == "POST":
        form = SignupStep1Form(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password1']
            domain = split_email_domain(email)

            existing_org = None
            if not is_generic_email_domain(domain):
                existing_org = Org.objects.filter(domain=domain).first()

            if existing_org:
                # Company org already exists -> create pending user & join request
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        password=password,
                        org=existing_org,
                        role=User.ROLE_OPERATOR,
                        status=User.STATUS_PENDING,
                    )
                    OrgJoinRequest.objects.create(org=existing_org, user=user)

                # TODO: send actual email notification to org admin(s)
                return render(request, 'accounts/signup_pending.html', {
                    "org": existing_org,
                    "email": email,
                })

            # Else: generic OR first company user -> go to org step
            request.session['signup_email'] = email
            request.session['signup_password'] = password
            request.session['signup_domain'] = domain
            return redirect('signup_org')
    else:
        form = SignupStep1Form()

    return render(request, 'accounts/signup_step1.html', {"form": form})


@require_http_methods(["GET", "POST"])
def signup_org(request):
    """
    Step 2: ask for Org Name, then create org + admin user.
    Handles:
    - generic email domains
    - first user for a company domain
    """
    email = request.session.get('signup_email')
    password = request.session.get('signup_password')
    domain = request.session.get('signup_domain')

    if not email or not password:
        # If step1 data missing, send back to step1
        return redirect('signup')

    if request.method == "POST":
        form = SignupOrgForm(request.POST)
        if form.is_valid():
            org_name = form.cleaned_data['org_name']

            with transaction.atomic():
                org_domain = None if is_generic_email_domain(domain) else domain

                org, created = Org.objects.get_or_create(
                    domain=org_domain,
                    defaults={"name": org_name},
                )
                # If org existed but had no name, we could update it (edge case)
                if not created and not org.name:
                    org.name = org_name
                    org.save()

                user = User.objects.create_user(
                    email=email,
                    password=password,
                    org=org,
                    role=User.ROLE_ADMIN,
                    status=User.STATUS_ACTIVE,
                )

            # Clean up session
            for key in ['signup_email', 'signup_password', 'signup_domain']:
                request.session.pop(key, None)

            # Auto-login the new admin
            login(request, user)
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = SignupOrgForm()

    return render(request, 'accounts/signup_org.html', {
        "form": form,
        "email": email,
    })

@login_required
def org_join_requests_list(request):
    """
    List pending join requests for the current user's organisation.
    Only accessible to org admins.
    """
    user = request.user

    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "You do not have permission to view this page.")
        return redirect('dashboard')

    pending_requests = OrgJoinRequest.objects.filter(
        org=user.org,
        is_approved=False,
        user__status=User.STATUS_PENDING,
    ).select_related('user')

    return render(request, 'accounts/org_requests.html', {
        "pending_requests": pending_requests,
        "org": user.org,
    })


@login_required
@require_http_methods(["POST"])
def approve_org_join_request(request, request_id):
    """
    Approve a pending join request in the current admin's organisation.
    - Marks join request as approved
    - Sets user.status = ACTIVE
    """
    user = request.user

    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('dashboard')

    join_request = get_object_or_404(
        OrgJoinRequest,
        id=request_id,
        org=user.org,
        is_approved=False,
    )

    # Approve
    join_request.is_approved = True
    join_request.save()

    join_user = join_request.user
    join_user.status = User.STATUS_ACTIVE
    join_user.save()

    # TODO: optional – send email notification to join_user

    messages.success(request, f"{join_user.email} has been approved and can now use Labelcraft.")
    return redirect('org_join_requests')


@login_required
@require_http_methods(["GET", "POST"])
def verify_email(request):
    user = request.user

    if user.email_is_verified:
        messages.info(request, "Your email is already verified.")
        return redirect("dashboard")

    # resend on GET (simple + works)
    if request.method == "GET":
        otp_row, raw = EmailOTP.create_otp(
            email=user.email,
            purpose=EmailOTP.PURPOSE_VERIFY,
            user=user,
            ttl_minutes=10,
        )
        send_mail(
            subject="Your Labelcraft verification OTP",
            message=f"Your OTP is {raw}. It expires in 10 minutes.",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return render(request, "accounts/verify_email.html", {
            "email": user.email,
        })

    # POST = confirm OTP
    raw_otp = (request.POST.get("otp") or "").strip()

    latest = EmailOTP.objects.filter(
        email=user.email,
        purpose=EmailOTP.PURPOSE_VERIFY,
    ).order_by("-created_at").first()

    if not latest:
        messages.error(request, "No OTP found. Please click Verify again.")
        return redirect("verify_email")

    ok = latest.verify(raw_otp)
    if not ok:
        messages.error(request, "Invalid/expired OTP. Please try again.")
        return redirect("verify_email")

    user.email_is_verified = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_is_verified", "email_verified_at"])

    messages.success(request, "Email verified successfully.")
    return redirect("dashboard")

@require_http_methods(["GET", "POST"])
def forgot_password(request):
    """
    Flow:
    1) User enters email + new password + confirm → Send OTP
    2) OTP input appears → Confirm Reset
    """
    if request.method == "GET":
        # clear any stale session state
        request.session.pop("fp_email", None)
        request.session.pop("fp_password", None)
        return render(request, "accounts/forgot_password.html", {"step": "start"})

    action = (request.POST.get("action") or "").strip()

    if action == "send_otp":
        email = (request.POST.get("email") or "").strip().lower()
        pw1 = request.POST.get("password1") or ""
        pw2 = request.POST.get("password2") or ""

        if not email:
            messages.error(request, "Enter your email.")
            return redirect("forgot_password")

        if pw1 != pw2 or not pw1:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/forgot_password.html", {"step": "start", "email": email})

        # Don’t reveal existence too much; but you do want reset only if user exists.
        u = User.objects.filter(email=email).first()
        if not u:
            messages.info(request, "If that email exists, we sent an OTP.")
            return render(request, "accounts/forgot_password.html", {"step": "otp", "email": email})

        otp_row, raw = EmailOTP.create_otp(
            email=email,
            purpose=EmailOTP.PURPOSE_RESET,
            user=u,
            ttl_minutes=10,
        )
        send_mail(
            subject="Your Labelcraft password reset OTP",
            message=f"Your OTP is {raw}. It expires in 10 minutes.",
            from_email=None,
            recipient_list=[email],
            fail_silently=False,
        )

        # store email + new password in session until OTP verifies
        request.session["fp_email"] = email
        request.session["fp_password"] = pw1

        messages.success(request, "OTP sent. Enter it to reset password.")
        return render(request, "accounts/forgot_password.html", {"step": "otp", "email": email})

    if action == "confirm_reset":
        email = request.session.get("fp_email") or ""
        new_password = request.session.get("fp_password") or ""
        raw_otp = (request.POST.get("otp") or "").strip()

        if not email or not new_password:
            messages.error(request, "Session expired. Please try again.")
            return redirect("forgot_password")

        u = User.objects.filter(email=email).first()
        if not u:
            messages.error(request, "Invalid request. Try again.")
            return redirect("forgot_password")

        latest = EmailOTP.objects.filter(
            email=email,
            purpose=EmailOTP.PURPOSE_RESET,
        ).order_by("-created_at").first()

        if not latest or not latest.verify(raw_otp):
            messages.error(request, "Invalid/expired OTP.")
            return render(request, "accounts/forgot_password.html", {"step": "otp", "email": email})

        u.set_password(new_password)
        u.save(update_fields=["password"])

        # cleanup
        request.session.pop("fp_email", None)
        request.session.pop("fp_password", None)

        messages.success(request, "Password updated. Please login.")
        return redirect("login")

    messages.error(request, "Invalid action.")
    return redirect("forgot_password")