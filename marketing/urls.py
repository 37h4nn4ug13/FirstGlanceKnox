from django.urls import path
from . import views

app_name = 'marketing'
urlpatterns = [
    path('', views.home, name='home'),
    path('residential/', views.audience, {'kind': 'residential'}, name='residential'),
    path('commercial/', views.audience, {'kind': 'commercial'}, name='commercial'),
    path('services/<slug:slug>/', views.service, name='service'),
    path('gallery/', views.gallery, name='gallery'),
    path('quote/', views.quote, name='quote'),
    path('quote/received/', views.quote_success, name='quote_success'),
    path('about/', views.page, {'slug': 'about'}, name='about'),
    path('service-areas/', views.page, {'slug': 'areas'}, name='areas'),
    path('contact/', views.page, {'slug': 'contact'}, name='contact'),
    path('faq/', views.page, {'slug': 'faq'}, name='faq'),
    path('privacy/', views.page, {'slug': 'privacy'}, name='privacy'),
    path('terms/', views.page, {'slug': 'terms'}, name='terms'),
    path('robots.txt', views.robots, name='robots'),
    path('sitemap.xml', views.sitemap, name='sitemap'),
]
