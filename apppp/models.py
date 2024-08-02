from django.db import models

class Image(models.Model):
    image = models.ImageField(upload_to='images/')
    aws_url = models.URLField(max_length=200, blank=True)
    analysis_results = models.JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.image.name

class Questionnaire(models.Model):
    age_range = models.CharField(max_length=20)
    skin_type = models.CharField(max_length=20)
    allergies = models.CharField(max_length=255, blank=True, null=True)
    acne_frequency = models.CharField(max_length=20)
    wrinkle_concerns = models.CharField(max_length=20)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Questionnaire {self.id}"
