# LogModel/forms.py
from django import forms
from django.forms import TextInput
from .models import Log  # or any model you're working with

class DateForm(forms.Form):
    date = forms.DateField(
        widget=TextInput(attrs={
            'id': 'jalali-date',
            'placeholder': 'تاریخ را انتخاب کنید',
            'autocomplete': 'off'
        }),
        required=False
    )
