from django.urls import path
from .views import ImageUploadView, ImageDetailView, QuestionnaireView

urlpatterns = [
    path('upload/', ImageUploadView.as_view(), name='image-upload'),
    path('image/<int:pk>/', ImageDetailView.as_view(), name='image-detail'),
    path('questionnaire/', QuestionnaireView.as_view(), name='questionnaire'),
]
