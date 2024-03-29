from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth.forms import UserCreationForm


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
        max_length=254,
        required=True,
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        required=True)


# class CustomSignupForm(UserCreationForm):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         for field_name, field in self.fields.items():
#             if isinstance(field.widget, forms.TextInput) or isinstance(field.widget, forms.EmailInput) or isinstance(
#                     field.widget, forms.PasswordInput):
#                 field.widget.attrs.update({'class': 'form-control'})
#             if field.label:
#                 field.label = field.label.capitalize()  # Capitalize the label
#                 field.label_classes = ['form-label']  # Add form-label class to label
#
#     class Meta(UserCreationForm.Meta):
#         fields = ['username', 'email', 'password1', 'password2']


class CustomSignupForm(UserCreationForm):
    username = forms.CharField(
        label="Username",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username', 'id': 'username'}),
        max_length=254,
        required=True,
    )
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email', 'id': 'email'}),
        required=True
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password', 'id': 'password'}),
        max_length=254,
        required=True,
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(
            attrs={'class': 'form-control', 'placeholder': 'Confirm Password', 'id': 'confirmPassword'}),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.label_classes = ['form-label']

    class Meta(UserCreationForm.Meta):
        fields = ['username', 'email', 'password1', 'password2']
