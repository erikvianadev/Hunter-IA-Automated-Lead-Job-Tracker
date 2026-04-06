from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'tags', views.TagViewSet, basename='tag')
router.register(r'jobs', views.JobViewSet, basename='job')
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'applications', views.JobApplicationViewSet, basename='jobapplication')

urlpatterns = [
    path('api/', include(router.urls)),
]
