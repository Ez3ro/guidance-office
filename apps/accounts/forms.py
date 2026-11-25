from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm

from apps.core.forms import BaseModelForm, BootstrapFormMixin

from .models import User


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass


class UserForm(BaseModelForm):
    fieldsets = [
        ("Account", ["username", "first_name", "last_name", "email", "position"]),
        ("Access", ["role", "is_cpc_member", "is_active"]),
    ]

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "position",
            "role",
            "is_cpc_member",
            "is_active",
        ]
        help_texts = {
            "is_active": "Untick to block sign-in. Accounts are deactivated, never deleted, "
            "so the audit trail stays intact."
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    def clean_role(self):
        role = self.cleaned_data["role"]
        editing_self = self.instance.pk and self.user and self.instance.pk == self.user.pk
        if editing_self and role != self.instance.role:
            raise forms.ValidationError("You can't change your own role.")
        return role

    def clean_is_active(self):
        active = self.cleaned_data["is_active"]
        editing_self = self.instance.pk and self.user and self.instance.pk == self.user.pk
        if editing_self and not active:
            raise forms.ValidationError("You can't deactivate your own account.")
        return active


class TemporaryPasswordMixin(forms.Form):
    temporary_password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        help_text="The user must change this the first time they sign in.",
    )

    def clean_temporary_password(self):
        password = self.cleaned_data["temporary_password"]
        user = getattr(self, "instance", None) or getattr(self, "target_user", None)
        password_validation.validate_password(password, user)
        return password


class UserCreateForm(TemporaryPasswordMixin, UserForm):
    fieldsets = UserForm.fieldsets + [("Temporary password", ["temporary_password"])]

    class Meta(UserForm.Meta):
        pass

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["temporary_password"])
        user.must_change_password = True
        if commit:
            user.save()
        return user


class ResetPasswordForm(BootstrapFormMixin, TemporaryPasswordMixin):
    def __init__(self, *args, target_user=None, **kwargs):
        self.target_user = target_user
        super().__init__(*args, **kwargs)
