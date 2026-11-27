from django.db import models


class BibliographyEntry(models.Model):
    date_received = models.DateField()
    accession_number = models.CharField(max_length=50, unique=True)
    call_number = models.CharField(max_length=100)
    title = models.CharField(max_length=500)
    year = models.IntegerField()
    author = models.CharField(max_length=255)

    
    edition = models.CharField(blank=True, max_length=50, null=True)
    volume = models.CharField(blank=True, max_length=50, null=True)
    pages = models.CharField(blank=True, max_length=50, null=True)
    dealer = models.CharField(blank=True, max_length=255, null=True)
    price = models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)
    place_of_publication = models.CharField(blank=True, max_length=255, null=True)
    publisher = models.CharField(blank=True, max_length=255, null=True)
    isbn = models.CharField(blank=True, max_length=50, null=True)
    recommended_by = models.CharField(blank=True, max_length=255, null=True)
    department = models.CharField(blank=True, max_length=100, null=True)
    section = models.CharField(blank=True, max_length=100, null=True)
    budget_charge = models.CharField(blank=True, max_length=100, null=True)
    po_number = models.CharField(blank=True, max_length=100, null=True)
    si_number = models.CharField(blank=True, max_length=100, null=True)
    contents = models.CharField(blank=True, max_length=100, null=True)

    def __str__(self):
        if self.author:
            return f"{self.title} by {self.author}"
        return self.title
    
    
    
    