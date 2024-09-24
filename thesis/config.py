import os
from dotenv import load_dotenv
from enum import Enum


load_dotenv()  # This loads the variables from .env

class Config:
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER')
    UPLOAD_PEOPLE_FOLDER = os.getenv('UPLOAD_PEOPLE_FOLDER')
    UPLOAD_DIGITAL_ARTWORK_FOLDER = os.getenv('UPLOAD_DIGITAL_ARTWORK_FOLDER')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    AWS_DEFAULT_REGION=os.getenv('AWS_DEFAULT_REGION')
    TMP_DIR=os.getenv('TMP_DIR')
    AWS_ACCESS_KEY_ID=os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_KEY=os.getenv('AWS_SECRET_KEY')
    APP_SECRET_KEY=os.getenv('APP_SECRET_KEY')
    BUCKET=os.getenv('BUCKET')
    CONFIDENCE=70
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/Users/elenapetrova/.google-cloud-credentials/grand-signifier-427003-s4-d8bc4689bb18.json"
    GROQ_API_KEY =os.getenv("GROQ_API_KEY")
    GROQ_MODEL_NAME=os.getenv("GROQ_MODEL_NAME")
    AUDIO_DIR=os.getenv("AUDIO_DIR")
    VIDEO_DIR=os.getenv("VIDEO_DIR")
    PINECONE_API_KEY=os.getenv("PINECONE_API_KEY")
    VECTOR_EMBEDDING_MODEL=os.getenv("VECTOR_EMBEDDING_MODEL")
    VECTOR_INDEX_NAME=os.getenv("VECTOR_INDEX_NAME") 
    USE_SERVERLESS=os.getenv("USE_SERVERLESS") 
    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY")
    GOOGLE_CREDS=os.getenv("GOOGLE_CREDS")
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.getenv('SECRET_KEY')

class MediaType(Enum):
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"
    INTRO_AUDIO = "intro_audio"

class UserMediaType(Enum):
    CHAT_AUDIO = "chat_audio"
    CHAT_VIDEO = "chat_video"    

class TextType(Enum):
    SHORT = 'short'
    STYLE = 'style'
    LONG = 'long'
    LABELS = "labels"
    INTRO = "intro"


class UploadType(Enum):
    UPLOAD = 'UPLOAD'
    PEOPLE = 'PEOPLE'
    ART = 'ART'    