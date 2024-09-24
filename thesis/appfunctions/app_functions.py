from components.artwork_animator_original import ArtworkAnimator
from components.database import DatabaseManager, ArtContent, Art, ArtUserContent
from config import MediaType, UserMediaType
from components.groq_llama import ArtworkInfo
import traceback
from flask import current_app
from flask_login import current_user
from threading import Lock

class AnimationStatus:
    def __init__(self):
        self.complete = False
        self.video_file = None
        self.video_path = None
        self.error = None
        self.lock = Lock()

    def set_complete(self, video_file, video_path):
        with self.lock:
            self.complete = True
            self.video_file = video_file
            self.video_path = video_path

    def set_error(self, error):
        with self.lock:
            self.complete = True
            self.error = error

    def get_status(self):
        with self.lock:
            return {
                "complete": self.complete,
                "video_file": self.video_file,
                "video_path": self.video_path,
                "error": self.error
            }
        
animation_status = AnimationStatus()

def add_art_content(art_id: int, content_type: str, content_url: str) -> ArtContent:
    return DatabaseManager.add_art_content(art_id, content_type, content_url)

def add_art(artwork_info: ArtworkInfo, user_id: int, file_id: int) -> Art:
    return DatabaseManager.save_art_to_db(artwork_info, user_id, file_id)

def add_art_user_content(art_id: int, user_id: int, content: str, content_type: str) -> ArtUserContent:
    return DatabaseManager.add_art_user_content(art_id, user_id, content, content_type)

def animate_artwork_task(app, image_uri, animation_audio_path, intro_story, artist, artwork, isportrait=False, art_id=None,timestamp=False,content_type=MediaType.VIDEO,user_id=None):
    with app.app_context():
        try:
            print("timestamp in animate_artwork_task")
            print(timestamp)  
            animator = ArtworkAnimator(image_uri)
            
            if animation_audio_path is None:
                raise ValueError("animation_audio_path is None")
            
            if not animation_audio_path.endswith('.mp3'):
                raise ValueError(f"Unexpected audio file format: {animation_audio_path}")
            
            animation_audio_path_full=current_app.config["AUDIO_DIR"]+"/"+animation_audio_path

            if isportrait:
                video_file_name, video_output_path = animator.create_animation(
                    animation_audio_path_full, 
                    intro_story,
                    f"{artist}_{artwork}_speaking",
                    timestamp=timestamp
                )
            else:
                video_file_name, video_output_path = animator.create_animations_for_non_portraits(
                    animation_audio_path_full, 
                    f"{artist}_{artwork}_speaking",
                    timestamp=timestamp
                )    
            
            # Save video content to database
            if art_id:
                if content_type.value==MediaType.VIDEO.value:
                    add_art_content(art_id, MediaType.VIDEO, video_file_name)
                elif content_type.value==UserMediaType.CHAT_VIDEO.value:
                    add_art_user_content(art_id,user_id,video_file_name,UserMediaType.CHAT_VIDEO)
            
            animation_status.set_complete(video_file_name, video_output_path)
            
        except Exception as e:
            print(f"Animation failed: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            animation_status.set_error(str(e))