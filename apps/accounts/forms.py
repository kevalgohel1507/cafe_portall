"""apps/accounts/forms.py"""
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    phone = forms.CharField(max_length=15, required=False)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = CustomUser.ROLE_USER
        if commit:
            user.save()
        return user


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Username or Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))

    def clean(self):
        """
        Support login with username (default) and with email.
        If multiple users share an email, authenticate against each until a match is found.
        """
        identifier = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        try:
            return super().clean()
        except forms.ValidationError as original_error:
            if not (identifier and password and '@' in identifier):
                raise

            candidates = CustomUser.objects.filter(email__iexact=identifier)
            for candidate in candidates:
                user = authenticate(
                    self.request,
                    username=candidate.get_username(),
                    password=password,
                )
                if user is not None:
                    self.user_cache = user
                    self.confirm_login_allowed(user)
                    self.cleaned_data['username'] = user.get_username()
                    return self.cleaned_data

            raise original_error


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'bio', 'avatar', 'date_of_birth', 'address']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class AdminUserCreateForm(UserCreationForm):
    role = forms.ChoiceField(choices=CustomUser.ROLE_CHOICES)

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'password1', 'password2']


class AdminUserEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'phone', 'role', 'is_active', 'is_verified']
