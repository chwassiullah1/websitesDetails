from django.urls import path
from django.contrib.auth.views import LoginView
from home import views
from home.forms import CustomLoginForm
from home.views import SignUpView

urlpatterns = [
    path('', views.home, name='home'),
    path('run_scraper', views.run_scraper, name='run_scraper'),
    path('scrape_email_and_links', views.scrape_email_and_links, name='scrape_email_and_links'),
    path('signup', SignUpView.as_view(), name='signup'),

    path('login',
         LoginView.as_view(template_name='login.html', success_url='home', authentication_form=CustomLoginForm),
         name='login'),
    path('logout', views.logout_view, name='logout'),
]
