from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'tags', views.TagViewSet, basename='tag')
router.register(r'jobs', views.JobViewSet, basename='job')
router.register(r'leads', views.LeadViewSet, basename='lead')
router.register(r'applications', views.JobApplicationViewSet, basename='jobapplication')
router.register(r'saved-jobs', views.SavedJobViewSet, basename='savedjob')
router.register(r'resumes', views.ResumeViewSet, basename='resume')
router.register(r'matches', views.JobMatchViewSet, basename='match')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/', include('hunter.api.urls')),
    path(
        'api/billing/plans/',
        views.BillingViewSet.as_view({'get': 'plans'}),
        name='billing-plans',
    ),
    path(
        'api/billing/subscription/',
        views.BillingViewSet.as_view({'get': 'subscription'}),
        name='billing-subscription',
    ),
    path(
        'api/billing/subscribe/',
        views.BillingViewSet.as_view({'post': 'subscribe'}),
        name='billing-subscribe',
    ),
    path(
        'api/billing/cancel/',
        views.BillingViewSet.as_view({'post': 'cancel'}),
        name='billing-cancel',
    ),
]
