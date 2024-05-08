from django.urls import path
from django.contrib.auth.views import LoginView
from home import views
from home.forms import CustomLoginForm
from home.views import SignUpView

urlpatterns = [
    path('', views.home, name='home'),
    path('run_scraper', views.run_scraper, name='run_scraper'),
    path('add_jobs', views.add_jobs, name='add_jobs'),
    path('signup', SignUpView.as_view(), name='signup'),
    path('view_jobs', views.view_jobs, name='view_jobs'),
    path('validate_emails', views.validate_emails, name='validate_emails'),
    path('add_and_review/<int:pk>/', views.add_and_review, name='add_and_review'),

    path('login',
         LoginView.as_view(template_name='login.html', success_url='home', authentication_form=CustomLoginForm),
         name='login'),
    path('logout', views.logout_view, name='logout'),
]
