from django.urls import path
from process_one import views

urlpatterns = [
    path('run_scraper', views.run_scraper, name='run_scraper'),
    path('search_data', views.search_data, name='search_data'),
]
