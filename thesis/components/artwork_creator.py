from openai import OpenAI
from PIL import Image
import requests
from io import BytesIO
import random
from werkzeug.datastructures import FileStorage


class ArtworkCreator:
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.art_styles = [
            "impressionist", "cubist", "surrealist", "abstract expressionist",
            "pop art", "minimalist", "digital art", "watercolor", "oil painting",
            "street art", "concept art", "pixel art"
        ]
        self.color_palettes = [
            "vibrant", "pastel", "monochromatic", "complementary", "analogous",
            "warm", "cool", "earthy", "neon", "muted"
        ]

    #playing around
    def generate_from_user_prompt(self, user_input, style=None, palette=None, num_prompts=1):
        if style is None:
            style = random.choice(self.art_styles)
        if palette is None:
            palette = random.choice(self.color_palettes)
        
        description = user_input
        labels = user_input.split()  # Simplistic label extraction

        base_prompt = f"Create art about {user_input}"

        prompts = []
        for _ in range(num_prompts):
            additional_instructions = random.choice([
                "Focus on texture and depth.",
                "Emphasize contrast and shadows.",
                "Incorporate geometric shapes.",
                "Use bold, expressive brushstrokes.",
                "Create a dreamlike atmosphere.",
                "Blend reality with fantasy elements."
            ])

            prompt = f"{base_prompt}Style: {style}\nColor palette: {palette}\nAdditional instructions: {additional_instructions}"
            prompts.append(prompt)

        return prompts
        

    def generate_art_prompts(self, labels, description, num_prompts=3):
        base_prompt = f"Create art inspired by the following:\nDescription: {description}\nKey elements: {', '.join(labels)}\n"
        
        prompts = []
        for _ in range(num_prompts):
            style = random.choice(self.art_styles)
            palette = random.choice(self.color_palettes)
            additional_instructions = random.choice([
                "Focus on texture and depth.",
                "Emphasize contrast and shadows.",
                "Incorporate geometric shapes.",
                "Use bold, expressive brushstrokes.",
                "Create a dreamlike atmosphere.",
                "Blend reality with fantasy elements."
            ])
            
            prompt = f"{base_prompt}Style: {style}\nColor palette: {palette}\nAdditional instructions: {additional_instructions}"
            prompts.append(prompt)
        
        return prompts

    def create_digital_art(self, labels, description, num_prompts=3, images_per_prompt=1, palette=None, user_input=None):
        if user_input == None:
            prompts = self.generate_art_prompts(labels, description, num_prompts)
        else:
            prompts = self.generate_from_user_prompt(user_input, description, palette)
        all_image_urls = []
        
        for prompt in prompts:
            try:
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=images_per_prompt,
                )
                image_urls = [item.url for item in response.data]
                all_image_urls.extend(image_urls)
            except Exception as e:
                print(f"Error generating digital art: {e}")
        
        return all_image_urls, prompts

    def get_image_content(self, image_url):
        try:
            response = requests.get(image_url)
            return BytesIO(response.content)
        except Exception as e:
            print(f"Error fetching image content: {e}")
            return None

    def create_file_storage(self, image_content, filename):
        file = FileStorage(
            stream=image_content,
            filename=filename,
            content_type="image/png"
        )
        return file