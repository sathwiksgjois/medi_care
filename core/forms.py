from django import forms
from django.contrib.auth.models import User
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    # Add email field from User model
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        })
    )
    
    class Meta:
        model = UserProfile
        fields = ['phone_number', 'date_of_birth', 'address', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial email value from user
        if self.instance and self.instance.user:
            self.fields['email'].initial = self.instance.user.email
        
        for field in self.fields:
            if field != 'email':  # Skip email as we already set its class
                self.fields[field].widget.attrs.update({
                    'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
                })

    def save(self, commit=True):
        profile = super().save(commit=False)
        if commit:
            profile.save()
            # Update the user's email
            user = profile.user
            user.email = self.cleaned_data['email']
            user.save()
        return profile