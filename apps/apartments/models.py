from django.db import models

class Apartment(models.Model):
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Apartment'
        verbose_name_plural = 'Apartments'
