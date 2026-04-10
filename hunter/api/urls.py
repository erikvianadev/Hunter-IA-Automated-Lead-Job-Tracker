from django.urls import path

from .views import ScrapeJobsView

urlpatterns = [
    path("scrape/", ScrapeJobsView.as_view(), name="scrape-jobs"),
]
