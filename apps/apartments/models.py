from django.db import models

class Apartment(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=12.9716)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=77.5946)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Apartment'
        verbose_name_plural = 'Apartments'
