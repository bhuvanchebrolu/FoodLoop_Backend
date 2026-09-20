from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from apps.common.views_activity import UserActivityListView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.users.urls')),
    path('api/users/', include('apps.users.urls_users')),
    path('api/admin/', include('apps.users.urls_admin')),
    path('api/apartments/', include('apps.apartments.urls')),
    path('api/foods/', include('apps.foods.urls')),
    path('api/shares/', include('apps.shares.urls')),
    path('api/reports/', include('apps.reports.urls')),
    path('api/activity/', UserActivityListView.as_view(), name='user-activity'),
    path('api/', include('apps.notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
