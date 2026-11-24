from django import forms
from .models import BibliographyEntry


class BibliographyEntryForm(forms.ModelForm):
    date_received = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    accession_number = forms.CharField(required=True)
    call_number = forms.CharField(required=True)
    author = forms.CharField(required=True)
    title = forms.CharField(required=True)
    year = forms.IntegerField(
        required=True,
        # error_messages={'required': 'Year is required for manual encoding.'}
    )

    class Meta:
        model = BibliographyEntry
        fields = '__all__'
    
        
class UploadFileForm(forms.Form):
    file = forms.FileField()
    
    
    