import os
import requests
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from django.http import JsonResponse
from rest_framework.views import APIView
from transformers import pipeline
from openai import OpenAI
import boto3
from .models import Image, Questionnaire
from .serializers import ImageSerializer, QuestionnaireSerializer
from decouple import config
from PIL import Image as PILImage
from io import BytesIO
import torch
import logging

# Load environment variables
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
OPENAI_API_KEY = config('OPENAI_API_KEY')

# AWS S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION_NAME
)

# Initialize the OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def delete_image(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Deleted local image file: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting image file: {e}")

class ImageUploadView(APIView):
    def post(self, request, *args, **kwargs):
        logger.debug("Received image upload request")
        image_serializer = ImageSerializer(data=request.data)
        if image_serializer.is_valid():
            try:
                image_instance = image_serializer.save()
                logger.debug(f"Image instance saved with ID: {image_instance.id}")
            except Exception as e:
                logger.error(f"Error saving image instance: {e}")
                return JsonResponse({"error": "Error saving image instance"}, status=500)
            
            try:
                file = image_instance.image
                file_path = file.name
                file.seek(0)
                file_data = file.read()
                dataBytesIO = BytesIO(file_data)
                image = PILImage.open(dataBytesIO)
                image.verify()
                file.seek(0)

                s3_client.upload_fileobj(
                    file,
                    AWS_STORAGE_BUCKET_NAME,
                    file.name
                )
                logger.debug(f"Image uploaded to S3: {file.name}")

                aws_url = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{file.name}"
                image_instance.aws_url = aws_url

                # Use Hugging Face API directly with the S3 URL
                device = 0 if torch.cuda.is_available() else -1
                acne_pipe = pipeline("image-classification", model="imfarzanansari/skintelligent-acne", device=device)
                wrinkle_pipe = pipeline("image-classification", model="imfarzanansari/skintelligent-wrinkles", device=device)

                acne_results = acne_pipe(aws_url)
                wrinkle_results = wrinkle_pipe(aws_url)

                image_instance.analysis_results = {
                    "acne": acne_results,
                    "wrinkles": wrinkle_results
                }
                logger.debug(f"Acne results: {acne_results}")
                logger.debug(f"Wrinkle results: {wrinkle_results}")

                # Retrieve the latest questionnaire data
                questionnaire = Questionnaire.objects.latest('submitted_at')
                questionnaire_data = {
                    'age_range': questionnaire.age_range,
                    'skin_type': questionnaire.skin_type,
                    'allergies': questionnaire.allergies,
                    'acne_frequency': questionnaire.acne_frequency,
                    'wrinkle_concerns': questionnaire.wrinkle_concerns
                }
                logger.debug(f"Questionnaire data: {questionnaire_data}")

                try:
                    detailed_analysis_prompt = f"""
Based on the provided data:

### Acne Levels:
- Level 0 (Mild Acne): {acne_results[0]['score']}
- Level -1 (Very Mild Acne): {acne_results[1]['score']}
- Level 1 (Moderate Acne): {acne_results[2]['score']}
- Level 2 (Moderate-Severe Acne): {acne_results[3]['score']}
- Level 3 (Severe Acne): {acne_results[4]['score']}

### Wrinkle Levels:
- Non-Wrinkle: {wrinkle_results[0]['score']}
- Wrinkle: {wrinkle_results[1]['score']}

### Detailed Analysis:
Provide personalized skincare recommendations, including:

#### Daily Skincare Routine:
1. **Cleansing**
   - Choose gentle cleansers that don't strip your skin of its natural oils. As you have dry skin, a mild, hydrating cleanser would be a good option.
2. **Toning**
   - Use an alcohol-free and fragrance-free toner, preferably with hydrating ingredients like hyaluronic acid and glycerin.
3. **Treatment**
   - If Acne is a concern but happens only rarely, you can use targeted treatments (like salicylic acid spot treatment) only when acne appear. Since your wrinkle concerns are significant, integrating Retinol products in your skincare routine could be beneficial. However, start with lower concentrations and increase gradually to prevent skin irritation.
4. **Moisturizing**
   - Hydrating moisturizers containing humectants (such as hyaluronic acid and glycerin) and occlusive agents (like shea butter or petroleum jelly) can help to lock in moisture and keep your skin hydrated.
5. **Sun Protection**
   - Regardless of your wrinkle concern, daily sunscreen application is crucial to protect your skin from the damaging UV rays. Use a broad-spectrum sunscreen with a minimum SPF 30.

#### Night Skincare Routine:
1. **Cleansing and Toning**
   - Same as the daily routine.
2. **Treatment**
   - You can use retinol products at night if it suits your skin, as it can be photosensitive.
3. **Moisturizing**
   - Use a richer night cream or sleeping pack for extensive hydration.
4. **Extra Care**
   - As per your needs, you can also incorporate under eye creams and lip balms.

#### Tips and Warnings:
1. **Introduce new products gradually**
   - Instead of changing your entire routine at once, introduce one new product at a time. This will allow you to monitor its effects more accurately.
2. **Patch test new treatments**
   - Before using a new product all over your face, conduct a patch test on a small area. This will help you see if your skin reacts negatively.
3. **Hydrate well**
   - Drinking enough water is just as important for your skin as any product. Aim for at least 8 glasses a day.
4. **Avoid touching your face**
   - Touching your face frequently can spread bacteria, leading to breakouts.
5. **Consult a dermatologist if needed**
   - If your skin problems persist or condition worsens, always consult with a dermatologist.
"""
                    response = client.chat.completions.create(
                        model="gpt-4",
                        messages=[
                            {"role": "user", "content": detailed_analysis_prompt}
                        ]
                    )
                    logger.debug("OpenAI API call successful")

                    detailed_analysis = response.choices[0].message.content.strip()
                except Exception as e:
                    logger.error(f"Error from OpenAI API: {e}")
                    detailed_analysis = "Detailed analysis not available due to an error."

                image_instance.analysis_results['detailed_analysis'] = detailed_analysis
                image_instance.save()

                delete_image(file_path)  # Delete the image after processing

                return Response({
                    'id': image_instance.id,
                    'analysis_results': image_instance.analysis_results
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error processing image upload: {e}")
                image_instance.delete()
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                # Ensure the temporary image file is deleted
                delete_image(file_path)

        logger.error(f"Image serializer errors: {image_serializer.errors}")
        return Response(image_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ImageDetailView(APIView):
    def get(self, request, pk, *args, **kwargs):
        image_instance = get_object_or_404(Image, pk=pk)
        serializer = ImageSerializer(image_instance)
        return Response(serializer.data)

class QuestionnaireView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = QuestionnaireSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
