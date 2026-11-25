from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy

from apps.audit.models import AuditEvent
from apps.audit.services import log_event
from apps.core.crud import Action, GenericCreateView, GenericListView, GenericUpdateView, ListFilter
from apps.core.permissions import require_cap
from apps.core.roles import Cap, Role

from .forms import LoginForm, ResetPasswordForm, StyledPasswordChangeForm, UserCreateForm, UserForm
from .models import User


class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_change.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.request.user
        if user.must_change_password:
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(self.request, user)
        return response


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"


class UserListView(GenericListView):
    model = User
    required_caps = (Cap.MANAGE_USERS,)
    title = "Users"
    columns = [
        ("Name", "display_name"),
        ("Username", "username"),
        ("Role", "get_role_display"),
        ("Position", "position"),
        ("CPC", "is_cpc_member"),
        ("Active", "is_active"),
        ("Last sign-in", "last_login"),
    ]
    search_fields = ["username", "first_name", "last_name", "email"]
    search_placeholder = "Search name, username or email…"
    filters = [
        ListFilter("role", "Role", Role.choices),
        ListFilter("is_active", "Status", [("True", "Active"), ("False", "Deactivated")]),
    ]
    create_url_name = "accounts:user_create"
    create_label = "Add user"


class UserCreateView(GenericCreateView):
    model = User
    form_class = UserCreateForm
    required_caps = (Cap.MANAGE_USERS,)
    title = "Add user"
    intro = (
        "Give the person a temporary password through a separate channel. "
        "They'll be asked to choose their own the first time they sign in."
    )
    success_message = "User created."

    def get_success_url(self):
        return reverse("accounts:user_list")

    def get_cancel_url(self):
        return reverse("accounts:user_list")


class UserUpdateView(GenericUpdateView):
    model = User
    form_class = UserForm
    required_caps = (Cap.MANAGE_USERS,)
    title = "Edit user"
    success_message = "User updated."

    def get_success_url(self):
        return reverse("accounts:user_list")

    def get_cancel_url(self):
        return reverse("accounts:user_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["extra_actions"] = [
            Action(
                "Reset password",
                reverse("accounts:user_reset_password", args=[self.object.pk]),
                "bi-key",
            )
        ]
        return ctx


@require_cap(Cap.MANAGE_USERS)
def reset_password(request, pk: int):
    target = get_object_or_404(User, pk=pk)
    form = ResetPasswordForm(request.POST or None, target_user=target)
    if request.method == "POST" and form.is_valid():
        target.set_password(form.cleaned_data["temporary_password"])
        target.must_change_password = True
        target.save()
        log_event(
            AuditEvent.Action.UPDATE,
            obj=target,
            changes={"password": ["(reset by administrator)", "(temporary)"]},
        )
        messages.success(request, f"Temporary password set for {target.display_name}.")
        return redirect("accounts:user_list")
    return render(
        request,
        "crud/form.html",
        {
            "form": form,
            "title": f"Reset password – {target.display_name}",
            "intro": "Their current sessions stay signed in until the password is used again.",
            "submit_label": "Set temporary password",
            "cancel_url": reverse("accounts:user_list"),
        },
    )
