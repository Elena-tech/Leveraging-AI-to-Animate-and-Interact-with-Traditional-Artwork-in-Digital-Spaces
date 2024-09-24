import face_recognition
import numpy as np
import cv2
import requests
from io import BytesIO
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip
from gtts import gTTS
import os
import pronouncing
from flask import current_app
from utils import get_timestamp_filename, get_filename
import traceback
import logging

class ArtworkAnimator:
    def __init__(self, image_url, max_size=1000):
        self.image_url = image_url
        self.max_size = max_size
        self.landmarks = None
        self.original_image = None
        self.mouth_shapes = None
        self.logger = logging.getLogger(__name__)

    def download_image(self):
        try:
            response = requests.get(self.image_url)
            response.raise_for_status()
            image_array = np.array(bytearray(response.content), dtype=np.uint8)
            self.original_image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)

            # Resize image if it's too large

            h, w = self.original_image.shape[:2]
            if max(h, w) > self.max_size:
                scale = self.max_size / max(h, w)
                self.original_image = cv2.resize(self.original_image, (int(w*scale), int(h*scale)))

            return cv2.cvtColor(self.original_image, cv2.COLOR_BGR2RGB)

        except requests.RequestException as e:
            raise Exception(f"Failed to download image: {str(e)}")

    def detect_landmarks(self):
        rgb_image = self.download_image()
        face_landmarks_list = face_recognition.face_landmarks(rgb_image)
        if face_landmarks_list:
            self.landmarks = face_landmarks_list[0]

    def calculate_mouth_shapes(self):
        if not self.landmarks or 'top_lip' not in self.landmarks or 'bottom_lip' not in self.landmarks:
            raise Exception("Invalid landmarks")

        top_lip = np.array(self.landmarks['top_lip'])
        bottom_lip = np.array(self.landmarks['bottom_lip'])

        top_center = np.mean(top_lip, axis=0)
        bottom_center = np.mean(bottom_lip, axis=0)
        mouth_height = np.linalg.norm(top_center - bottom_center)

        closed_mouth = {'top': top_lip, 'bottom': bottom_lip}

        open_factor = 2.0  # Increase this value for more pronounced mouth opening

        direction = (bottom_center - top_center) / np.linalg.norm(bottom_center - top_center)
        open_top = top_lip - direction * mouth_height * (open_factor - 1) / 2
        open_bottom = bottom_lip + direction * mouth_height * (open_factor - 1) / 2

        open_mouth = {'top': open_top, 'bottom': open_bottom}

        self.mouth_shapes = {'closed': closed_mouth, 'open': open_mouth}

    def apply_mouth_shape(self, new_mouth_shape):
        original_top = np.array(self.landmarks['top_lip'])
        original_bottom = np.array(self.landmarks['bottom_lip'])
        new_top = np.array(new_mouth_shape['top'])
        new_bottom = np.array(new_mouth_shape['bottom'])

        top_transform = new_top - original_top
        bottom_transform = new_bottom - original_bottom

        height, width = self.original_image.shape[:2]
        output = self.original_image.copy()

        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.fillPoly(mask, [original_top.astype(int)], 1)
        cv2.fillPoly(mask, [original_bottom.astype(int)], 1)

        for y in range(height):
            for x in range(width):
                if mask[y, x] == 1:
                    if cv2.pointPolygonTest(original_top, (x, y), False) >= 0:
                        distances = np.sum((original_top - [x, y])**2, axis=1)
                        closest_index = np.argmin(distances)
                        new_x = int(x + top_transform[closest_index][0])
                        new_y = int(y + top_transform[closest_index][1])
                    else:
                        distances = np.sum((original_bottom - [x, y])**2, axis=1)
                        closest_index = np.argmin(distances)
                        new_x = int(x + bottom_transform[closest_index][0])
                        new_y = int(y + bottom_transform[closest_index][1])
                    
                    if 0 <= new_x < width and 0 <= new_y < height:
                        output[new_y, new_x] = self.original_image[y, x]

        return output

    def phoneme_to_mouth_shape(self, phoneme):
        vowels = set('AEIOU')
        if phoneme in vowels:
            return self.mouth_shapes['open']
        else:
            return self.mouth_shapes['closed']

    def text_to_phonemes(self, text):
        words = text.split()
        phonemes = []
        for word in words:
            pronunciations = pronouncing.phones_for_word(word.lower())
            if pronunciations:
                phonemes.extend(pronunciations[0].split())
        return phonemes

    def generate_audio(self, text, output_path):
        tts = gTTS(text=text, lang='en')
        tts.save(output_path)
        return output_path

    def create_animation(self, audio_path, text, name, timestamp=True):
        
        print("timestamp_in_creation_animation")
        print(timestamp)

        if not self.landmarks:
            self.detect_landmarks()
    
        if not self.landmarks:
            print("Landmark detection failed. Falling back to non-portrait animation.")
            return self.create_animations_for_non_portraits(audio_path, name)
        
        if not self.mouth_shapes:
            self.calculate_mouth_shapes()
        
        if not self.mouth_shapes:
            print("Mouth shape calculation failed. Falling back to non-portrait animation.")
            return self.create_animations_for_non_portraits(audio_path, name)
        frames = []
        phonemes = [char.upper() for char in text if char.isalpha()]
        
        print(f"Number of phonemes: {len(phonemes)}")  # Debug print

        if not phonemes:
            raise ValueError("No valid phonemes found in the input text")

        for phoneme in phonemes:
            try:
                mouth_shape = self.phoneme_to_mouth_shape(phoneme)
                frame = self.apply_mouth_shape(mouth_shape)
                frames.append(ImageClip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).set_duration(0.1))
            except Exception as e:
                print(f"Error processing phoneme {phoneme}: {str(e)}")

        print(f"Number of frames: {len(frames)}")  # Debug print

        if not frames:
            raise ValueError("No frames were generated")

        video = concatenate_videoclips(frames)
        audio = AudioFileClip(audio_path)
        final_clip = video.set_audio(audio)
        if timestamp:
            video_file_name = get_timestamp_filename(name, "mp4")
        else:    
            video_file_name = get_filename(name, "mp4")
            
        video_output_path = os.path.join(current_app.config['VIDEO_DIR'], video_file_name)
        final_clip.write_videofile(video_output_path, fps=10)

        self.logger.info(f"Creating animation for non-portrait: audio_path={audio_path}, output_name={video_output_path}")

        return video_file_name, video_output_path
    
    def create_animations_for_non_portraits(self, audio_path, name, duration=10, fps=30,
                                        sway_intensity=0.3,
                                        shimmer_intensity=0.5,
                                        texture_intensity=0.3,
                                        zoom_intensity=0.2,
                                        particle_intensity=0.1,
                                        color_pulse_intensity=0.5,
                                        wind_effect_intensity=0.4,
                                        bloom_intensity=0.3,
                                        timestamp=True):
        print("timestamp")
        print(timestamp)
        if self.original_image is None:
            self.download_image()

        if self.original_image is None:
            raise ValueError("Failed to load image. Make sure a valid image URL was provided.")

        frames = []
        h, w = self.original_image.shape[:2]

        for i in range(int(duration * fps)):
            frame = self.original_image.copy()

            # 1. Reduced swaying motion
            M = np.float32([[1, 0.02 * np.sin(i * 0.1) * sway_intensity, 3 * np.sin(i * 0.1) * sway_intensity],
                            [-0.02 * np.sin(i * 0.1) * sway_intensity, 1, 3 * np.sin(i * 0.05) * sway_intensity]])
            frame = cv2.warpAffine(frame, M, (w, h))

            # 2. Enhanced light shimmer effect
            shimmer = np.random.normal(0, 20 * shimmer_intensity, frame.shape).astype(np.float32)
            frame = np.clip(frame.astype(np.float32) + shimmer, 0, 255).astype(np.uint8)

            # 3. Enhanced texture effect
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            edges = cv2.Laplacian(gray, cv2.CV_64F)
            edges = np.uint8(np.absolute(edges))
            frame = cv2.addWeighted(frame, 1, cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR), texture_intensity, 0)

            # 4. Subtle zoom effect
            scale = 1 + 0.0005 * i * zoom_intensity  # Very slow zoom
            M = cv2.getRotationMatrix2D((w/2, h/2), 0, scale)
            frame = cv2.warpAffine(frame, M, (w, h))

            # 5. Enhanced particle effect for brush strokes
            particle_layer = np.zeros_like(frame)
            for _ in range(int(200 * particle_intensity)):  # Number of particles
                x = np.random.randint(0, w)
                y = np.random.randint(0, h)
                color = frame[y, x].tolist()
                cv2.circle(particle_layer, (x, y), np.random.randint(1, 4), color, -1)
            frame = cv2.addWeighted(frame, 1 - particle_intensity, particle_layer, particle_intensity, 0)

            # 6. Enhanced color pulsing
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
            hsv[:,:,1] *= 1 + 0.2 * np.sin(i * 0.1) * color_pulse_intensity  # Saturation change
            hsv[:,:,2] *= 1 + 0.1 * np.sin(i * 0.2) * color_pulse_intensity  # Value change
            hsv = np.clip(hsv, 0, 255).astype(np.uint8)
            frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

            # 7. Wind effect (flowing motion)
            y, x = np.mgrid[0:h, 0:w]
            x_offset = 5 * np.sin(y / 30 + i * 0.2) * wind_effect_intensity
            flow = np.dstack((x + x_offset, y))
            frame = cv2.remap(frame, flow.astype(np.float32), None, cv2.INTER_LINEAR)

            # 8. Bloom effect (glow around bright areas)
            bright = cv2.threshold(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 200, 255, cv2.THRESH_BINARY)[1]
            bright = cv2.GaussianBlur(bright, (21, 21), 11)
            bright = cv2.cvtColor(bright, cv2.COLOR_GRAY2BGR)
            frame = cv2.addWeighted(frame, 1, bright, bloom_intensity, 0)

            # Convert BGR to RGB for MoviePy
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(ImageClip(frame_rgb).set_duration(1/fps))

        # Create video from frames
        video = concatenate_videoclips(frames)

        # Add audio
        audio = AudioFileClip(audio_path)
        final_clip = video.set_audio(audio)

        # Ensure the video duration matches the audio duration
        final_clip = final_clip.set_duration(audio.duration)

        # Save the video
        if timestamp:
            video_file_name = get_timestamp_filename(name, "mp4")
        else:    
            video_file_name = get_filename(name, "mp4")
            
        video_output_path = os.path.join(current_app.config['VIDEO_DIR'], video_file_name)
        final_clip.write_videofile(video_output_path, fps=fps)
        self.logger.info(f"Creating animation for non-portrait: audio_path={audio_path}, output_name={video_output_path}")
        
        return video_file_name, video_output_path