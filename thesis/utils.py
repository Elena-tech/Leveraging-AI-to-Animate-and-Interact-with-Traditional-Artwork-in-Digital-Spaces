import os
from flask import current_app
from components.aws import RunRekognition 
import time 
from components.artwork_recogniser import ArtworkRecogniser
from google.cloud import texttospeech
from google.oauth2 import service_account
import unicodedata
import re
from config import UploadType
from components.database import File



def save_art_file(file,art=UploadType.UPLOAD.value,thisfilename=""):
    if thisfilename=="":
        filename = file.filename
    else:
        filename=thisfilename
    split_tup = os.path.splitext(filename)
    # extracting the file name and extension
    file_extension = split_tup[1]
    file_actualname=split_tup[0]
    tmpfilename = file_actualname+time.strftime("%Y%m%d-%H%M%S") + file_extension
    if art==UploadType.UPLOAD.value:
        tmpfilename=filename
        filedir = current_app.config['UPLOAD_FOLDER']
    elif art==UploadType.PEOPLE.value:
        filedir = current_app.config['UPLOAD_PEOPLE_FOLDER']
    elif art==UploadType.ART.value:
        filedir = current_app.config['UPLOAD_DIGITAL_ARTWORK_FOLDER']
    
    existing_file = File.query.filter_by(filename=tmpfilename).first()
    if existing_file:
        print(f"This file has already been uploaded. Existing file: {existing_file.filename}")
        return existing_file.filename, existing_file.aws_url


    file.save(os.path.join(filedir, tmpfilename))
    # SAVE ON S3 too
    aws = RunRekognition()
    image_uri = aws.upload_to_bucket(tmpfilename, file.stream)
    # print(f"Image saved: {filedir}")
    print(f"Image saved on AWS: {image_uri}")
    return tmpfilename,image_uri

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def create_upload_folder():
    os.makedirs(current_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(current_app.config['UPLOAD_PEOPLE_FOLDER'], exist_ok=True)
    os.makedirs(current_app.config['UPLOAD_DIGITAL_ARTWORK_FOLDER'], exist_ok=True)

def get_image_labels(image_uri):
    aws = RunRekognition()
    labels = aws.get_labels(image_uri)
    artwork_recogniser = ArtworkRecogniser()
    results = artwork_recogniser.recognise_artwork(image_uri)
    print(results)
    return labels, results

def getaudio(story, name, gender=None, timestamp=True):
    if gender==None:
        gender='female'
    credentials = service_account.Credentials.from_service_account_file(current_app.config['GOOGLE_CREDS'])       
    client = texttospeech.TextToSpeechClient(credentials=credentials)

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=story)

    # Build the voice request
    if gender.lower() == 'male':
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-B",
            ssml_gender=texttospeech.SsmlVoiceGender.MALE
        )
    else:
        voice = texttospeech.VoiceSelectionParams(
            language_code="en-US",
            name="en-US-Wavenet-C",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Perform the text-to-speech request
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )

    # Generate audio file name
    if timestamp:
        audio_file_name = get_timestamp_filename(name, "mp3")
    else:    
        audio_file_name = get_filename(name, "mp3")

    audio_path = os.path.join(current_app.config['AUDIO_DIR'], audio_file_name)

    # The response's audio_content is binary.
    with open(audio_path, "wb") as out:
        out.write(response.audio_content)
    
    # Return both the file name and the full path
    return audio_file_name, audio_path    

def get_artist_and_painting(text):
    # Split the text into key-value pairs
    pairs = text.split(', ')
    
    painter_name = ''
    artwork = ''
    
    for pair in pairs:
        key, value = pair.split('=')
        if key == 'PainterName':
            painter_name = value
        elif key == 'Artwork':
            artwork = value
    
    return painter_name, artwork

def get_long_and_short_summary(text):
    
    short_summary = ''
    long_summary = ''
    
    # Extract ShortSummary
    short_summary_start = text.index("ShortSummary=[") + len("ShortSummary=[")
    short_summary_end = text.index("]", short_summary_start)
    short_summary = text[short_summary_start:short_summary_end]

    # Extract LongSummary
    long_summary_start = text.index("LongSummary=[") + len("LongSummary=[")
    long_summary_end = text.rindex("]")  # Use rindex to find the last occurrence of ']'
    long_summary = text[long_summary_start:long_summary_end]
    
    return short_summary, long_summary

def sanitize_string(string):
    # Remove accents
    string = ''.join(c for c in unicodedata.normalize('NFD', string)
                     if unicodedata.category(c) != 'Mn')
    # Remove non-ASCII characters
    string = re.sub(r'[^\x00-\x7F]+', '', string)
    # Replace spaces and other non-alphanumeric characters with underscores
    string = re.sub(r'[^a-zA-Z0-9]+', '_', string)
    # Ensure the string is lowercase
    return string.lower()

def get_timestamp_filename(name, extension="mp3"):
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    name_no_spaces = re.sub(r'[^\w\s-]', '', name.replace("'", ""))
    name_no_spaces = re.sub(r'\s+', '_', name_no_spaces)
    file_name = f"{name_no_spaces}_{timestamp}.{extension}"
    return file_name

def get_filename(name, extension="mp3"):
    name_no_spaces = re.sub(r'[^\w\s-]', '', name.replace("'", ""))
    name_no_spaces = re.sub(r'\s+', '_', name_no_spaces)
    file_name = f"{name_no_spaces}.{extension}"
    return file_name