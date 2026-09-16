from rest_framework import generics, permissions
from .models import Apartment
from .serializers import ApartmentSerializer

class ApartmentListView(generics.ListAPIView):
    queryset = Apartment.objects.all()
    serializer_class = ApartmentSerializer
    permission_classes = [permissions.AllowAny]
