from google.oauth2 import service_account
from google.cloud import vision
from flask import current_app
import io
import requests

class ArtworkRecogniser:
    def __init__(self):
        credentials = service_account.Credentials.from_service_account_file(current_app.config['GOOGLE_CREDS'])
        self.client = vision.ImageAnnotatorClient(credentials=credentials)
        
    def recognise_artwork(self, image_url):
        # Download the image
        response = requests.get(image_url)
        image_content = response.content

        image = vision.Image(content=image_content)

        # Performs label detection on the image file
        response = self.client.label_detection(image=image)
        print(response)
        labels = response.label_annotations
        
        # Performs web detection
        web_response = self.client.web_detection(image=image)
        print(web_response)
        web = web_response.web_detection

        # Get the best guess label
        if web.best_guess_labels:
            best_guess = web.best_guess_labels[0].label
        else:
            best_guess = "Unknown"

        # Get top 5 labels
        top_labels = [label.description for label in labels[:7]]
        
        # Get similar images
        similar_images = [image.url for image in web.visually_similar_images[:5]]
        # Get matching images
        matching_images = [image.url for image in web.full_matching_images[:3]]
        return {
            "best_guess": best_guess,
            "labels": top_labels,
            "similar_images": similar_images,
            "matching_images": matching_images
        }