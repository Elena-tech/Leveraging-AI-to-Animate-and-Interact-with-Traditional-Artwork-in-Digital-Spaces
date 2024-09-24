from config import Config, MediaType, UploadType, UserMediaType, TextType
from utils import save_art_file,allowed_file, create_upload_folder, get_image_labels, getaudio, get_artist_and_painting, get_long_and_short_summary
from components.groq_llama import GroqLlama, ArtworkFullInfo
from components.vector import VectorDB
from components.artwork_creator import ArtworkCreator
from components.database import db, DatabaseManager, ArtManager, Art, File, CreatedArt, ArtContent, ArtText, ArtUserContent
from appfunctions.app_functions import animate_artwork_task, animation_status

from flask import Flask, render_template, session, request, jsonify, redirect, url_for, current_app, send_from_directory, flash
import threading
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from typing import Dict, Any
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import traceback


app = Flask(__name__)
app.config.from_object(Config)

# Set up logging

DatabaseManager.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    DatabaseManager.init_database(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return DatabaseManager.get_user_by_id(int(user_id))

animation_complete = False
video_file_name = None
video_output_path = None

def save_file_to_db(filename, aws_url, user_id, is_user_upload=False) -> File:
    return DatabaseManager.add_file(filename, aws_url, user_id,is_user_upload)

def save_art_to_db(artwork_info: Dict[str, Any], user_id: int, file_id: int) -> Art:
    return DatabaseManager.save_art_to_db(artwork_info, user_id, file_id)

def add_art_content(art_id: int, content_type: str, content_url: str) -> ArtContent:
    return DatabaseManager.add_art_content(art_id, content_type, content_url)

def add_art_text(art_id: int, user_id: int, content: str, content_type: str) -> ArtText:
    return DatabaseManager.add_art_text(art_id, user_id, content, content_type)

def add_art_user_content(art_id: int, user_id: int, content: str, content_type: str) -> ArtUserContent:
    return DatabaseManager.add_art_user_content(art_id, user_id, content, content_type)

def save_created_art_to_db(filename: str, aws_url: str, user_id: int, file_id: int, 
                           is_random: bool, prompt: str, art_id: int, user_input: str = None) -> CreatedArt:
    
    return DatabaseManager.save_created_art_to_db(
        filename=filename,
        aws_url=aws_url,
        user_id=user_id,
        file_id=file_id,
        is_random=is_random,
        prompt=prompt,
        user_input=user_input,
        art_id=art_id
    )
      

@app.route('/api/upload', methods=['POST'])
@login_required
def api_upload_file():
    create_upload_folder()
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected for uploading'}), 400
    
    if file and allowed_file(file.filename):
        filename, image_uri = save_art_file(file)
        new_file_db = save_file_to_db(filename, image_uri, current_user.id)
        session['last_uploaded_file'] = {
                'id': new_file_db.id,
            }
        # Instead of returning JSON, redirect to the existing display route
        display_url = url_for('display_art', filename=filename, image_uri=image_uri, _external=True)
        
        return jsonify({
            'message': 'File successfully uploaded',
            'display_url': display_url
        }), 201
    
    return jsonify({'error': 'File type not allowed'}), 400

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = DatabaseManager.get_user_by_username(username)
        if user:
            flash('Username already exists.')
            return redirect(url_for('register'))
        
        new_user = DatabaseManager.add_user(username, email, password)
        login_user(new_user)
        return redirect(url_for('upload_file'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = DatabaseManager.get_user_by_username(username)
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('upload_file'))
        else:
            flash('Invalid username or password.')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def show_profile():
    uploaded_files = DatabaseManager.get_files_by_user(current_user.id,True)
    
    # Fetch the user's analyzed art
    analyzed_art = Art.query.filter_by(user_id=current_user.id).all()
    
    # Fetch the user's created art
    created_art = CreatedArt.query.filter_by(user_id=current_user.id).all()
    
    # Fetch art content and text for each analyzed art
    art_details = []
    for art in analyzed_art:
        content = ArtContent.query.filter_by(art_id=art.id).all()
        text = ArtText.query.filter_by(art_id=art.id).all()
        art_details.append({
            'art': art,
            'content': content,
            'text': text
        })
    
    return render_template('profile.html', 
                           user=current_user, 
                           files=uploaded_files, 
                           art_details=art_details,
                           created_art=created_art)

@app.route('/', methods=['GET', 'POST'])
@login_required
def upload_file():
    create_upload_folder()
    if request.method == 'POST':
        print(request.files)
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            existing_file = File.query.filter_by(filename=file.filename).first()
            if existing_file:
                print(f"This file has already been uploaded. Existing file: {existing_file.filename}")
                filename = existing_file.filename
                image_uri = existing_file.aws_url

                # Now check if this file exists for the current user
                user_file = File.query.filter_by(filename=file.filename, user_id=current_user.id).first()
                if user_file:
                    print("This file already exists for the current user.")
                    new_file_db = user_file  # Use the existing file record
                else:
                    print("File exists in the system but not for this user. Creating a new record for the user.")
                    new_file_db = save_file_to_db(filename, image_uri, current_user.id, True)
            else:
                # File doesn't exist for anyone, so save it
                filename, image_uri = save_art_file(file)
                new_file_db = save_file_to_db(filename, image_uri, current_user.id, True)
            
            session['last_uploaded_file'] = {
                'id': new_file_db.id,
            }
            print(image_uri)
            return redirect(url_for('display_art', filename=filename, image_uri=image_uri, file_id=new_file_db.id))
    return render_template('upload.html')
    pass

@app.route('/display/<filename>')
@login_required
def display_art(filename):
    global animation_complete, video_file_name, video_output_path
    animation_complete = False
    video_file_name = None
    video_output_path = None
    file_info = session.get('last_uploaded_file')
    
    # Get the file information from the database
    file = DatabaseManager.get_file_by_id(file_info['id'])
    if not file:
        flash("File not found in the database.", "error")
        return redirect(url_for('upload'))

    image_uri = file.aws_url

    # Check if art already exists for this file
    existing_art = DatabaseManager.get_art_by_file_id(file_info['id'])
    art_manager = ArtManager()
    myGroq = GroqLlama()

    if existing_art:
        # Art exists, use the existing information or copy for new user
        user_art = DatabaseManager.get_art_by_user_and_file(current_user.id, file_info['id'])
        if not user_art:
            user_art = art_manager.copy_art_for_user(existing_art, current_user.id)
        new_art_db = user_art
    else:
        # Art doesn't exist, process the image and create new art entry
        labels, results = get_image_labels(image_uri)
        art_result = myGroq.get_art(results)
        new_art_db = save_art_to_db(art_result, current_user.id, file_info['id'])
        
        # Create ArtworkFullInfo object
        artwork_info = ArtworkFullInfo(
            labels=labels,
            short_description=myGroq.get_short_history(art_result["Artwork"], art_result["PainterName"]),
            style_description="",  # You might want to add this if needed
            long_description=myGroq.get_long_history(art_result["Artwork"], art_result["PainterName"]),
            audio_file="",
            intro_audio_file="",
            video_file="",
            intro_story=f"I am {art_result['Artwork']} by {art_result['PainterName']}"
        )
        print(artwork_info)

        # Save to vector store
        vector_db = VectorDB()
        vector_db.store_artwork(artwork_info['long_description'], image_uri, art_result["Artwork"], art_result["PainterName"])

        # Generate audio files
        audio_file, _ = getaudio(artwork_info['short_description'], f"{art_result['PainterName']}_{art_result['Artwork']}", timestamp=False)
        artwork_info['audio_file'] = audio_file
        intro_story = f"I am {art_result['Artwork']} by {art_result['PainterName']}"
        artwork_info['intro_story']=intro_story
        animation_audio_file, _ = getaudio(intro_story, f"{art_result['PainterName']}_{art_result['Artwork']}_intro", gender=art_result["PersonGender"], timestamp=False)
        artwork_info['intro_audio_file'] = animation_audio_file

        # Ensure all content is added
        art_manager.ensure_art_content(new_art_db, artwork_info)

    session['last_art_file'] = {'id': new_art_db.id}

    # Fetch all art information at once
    artwork_full_info = art_manager.get_artwork_full_info(new_art_db.id)

    # Check if video exists
    video_content = artwork_full_info.get('video_file')
    if not video_content:
        # Video doesn't exist, start the animation thread
        timestamp=False
        animation_thread = threading.Thread(
            target=animate_artwork_task, 
            args=(app, image_uri,  artwork_full_info['intro_audio_file'], intro_story, new_art_db.painter_name, new_art_db.art_name, new_art_db.is_portrait, new_art_db.id, timestamp)
        )
        animation_thread.start()

    art_questions = myGroq.get_questions(new_art_db.art_name, new_art_db.painter_name)

    return render_template('display.html', 
                           filename=filename, 
                           image_uri=image_uri, 
                           labels=artwork_full_info['labels'], 
                           artist=new_art_db.painter_name, 
                           artwork=new_art_db.art_name,
                           audio_file=artwork_full_info['audio_file'],
                           video_file=video_content,
                           description=artwork_full_info['long_description'], 
                           gender=new_art_db.gender,
                           isportrait=new_art_db.is_portrait, 
                           questions=art_questions, 
                           art_id=new_art_db.id) 

@app.route('/talk_to_your_art', methods=['POST'])
@login_required
def talk_to_your_art():
    labels = request.form.get("labels")
    artist = request.form.get("artist")
    artwork = request.form.get("artwork")
    image_uri = request.form.get("image_uri")
    user_input = request.form.get('user_input')
    description = request.form.get('description')
    gender = request.form.get('gender')
    isportrait = request.form.get('isportrait') == 'True'
    art_id = request.form.get('art_id')  # Make sure to pass this from the form
    # Reset animation status
    animation_status.__init__()

    # Store the question
    new_question = DatabaseManager.add_art_question(art_id, current_user.id, user_input)

    myGroq = GroqLlama()
    answer = myGroq.get_answer(artwork, artist, description, user_input)

    # Update the question with the answer
    DatabaseManager.update_art_question_answer(new_question.id, answer)

    animation_audio_file, animation_audio_path = getaudio(answer, f"{artist}_{artwork}_chat", gender=gender,timestamp=True)
    print(f"Audio file saved at: {animation_audio_file}")  # Debug print

    # Save the audio content
    add_art_user_content(art_id,current_user.id,animation_audio_file,UserMediaType.CHAT_AUDIO)
    timestamp=True
    content_type=UserMediaType.CHAT_VIDEO    
    animation_thread = threading.Thread(
        target=animate_artwork_task, 
        args=(app, image_uri, animation_audio_file, answer, artist, artwork, isportrait, art_id, timestamp, content_type, current_user.id)
    )
    animation_thread.start()

    # Fetch all questions and answers for this artwork
    all_questions = DatabaseManager.get_art_questions(art_id,current_user.id)

    return render_template('video_talking.html', 
                           image_uri=image_uri, 
                           labels=labels, 
                           artist=artist, 
                           artwork=artwork,
                           answer=answer, 
                           question=user_input, 
                           description=description, 
                           gender=gender,
                           isportrait=isportrait,
                           all_questions=all_questions,
                           art_id=art_id)

@app.route('/create-personal-museum', methods=['POST'])
@login_required
def create_personal_museum():
    create_upload_folder()
    name = request.form['name']
    age = request.form['age']
    gender = request.form['gender']
    favorite_artists = request.form.getlist('favorite-artists[]')
    art_style = request.form['art-style']
    interests = request.form.getlist('interests[]')
    story = request.form['story']
    
    user_image = None
    if 'user-image' in request.files:
        user_image_file = request.files['user-image']
        if user_image_file.filename != '' and allowed_file(user_image_file.filename):
            filename, image_uri = save_art_file(user_image_file, UploadType.PEOPLE.value)
            user_image = image_uri
            print(filename)
            print(user_image)
    
    return render_template('personal_museum.html',
                           name=name,
                           age=age,
                           gender=gender,
                           favorite_artists=favorite_artists,
                           art_style=art_style,
                           interests=interests,
                           story=story,
                           user_image=user_image)

#playing around 

@app.route("/create_user_digital_art", methods=["POST"])
@login_required
def create_user_digital_art():
    labels = request.form.get("labels")
    artist = request.form.get("artist")
    artwork = request.form.get("artwork")
    art_id = request.form.get("art_id")
    user_input = request.form.get('user_input')
    palette = request.form.get('palette')
    
    style=DatabaseManager.get_art_text(art_id, TextType.STYLE)
    if style is None:
        myGroq = GroqLlama()
        style = myGroq.get_style(artist,artwork=artwork)
    
    labels_list = [label.strip() for label in labels.split(',')]
    
    digital_art_creator = ArtworkCreator(current_app.config['OPENAI_API_KEY'])
    image_urls, prompts = digital_art_creator.create_digital_art(labels_list, style, num_prompts=3, images_per_prompt=1, palette=palette, user_input=user_input)
    
    digital_art_files = []
    for i, (url, prompt) in enumerate(zip(image_urls, prompts)):
        image_content = digital_art_creator.get_image_content(url)
        if image_content:
            filename = f"digital_art_{i+1}.png"
            file = digital_art_creator.create_file_storage(image_content, filename)
            saved_filename, image_uri = save_art_file(file, art="ART", thisfilename=filename)
            if saved_filename:
                new_file = save_file_to_db(saved_filename, image_uri, current_user.id, False)
                created_art = save_created_art_to_db(
                    filename=saved_filename,
                    aws_url=image_uri,
                    user_id=current_user.id,
                    file_id=new_file.id,
                    is_random=False,  # You might want to add an option for this in the form
                    prompt=prompt,
                    art_id=art_id,
                    user_input=user_input
                )
                digital_art_files.append((saved_filename, image_uri,created_art.id))
    
    return render_template("digital_art.html", 
                           original_description=style, 
                           digital_art_files=digital_art_files, 
                           prompts=prompts,
                           user_input=user_input)

@app.route("/create_digital_art", methods=["POST"])
@login_required
def create_digital_art():
    labels = request.form.get("labels")
    artist = request.form.get("artist")
    artwork = request.form.get("artwork")
    art_id = request.form.get("art_id")
    
    description=DatabaseManager.get_art_text(art_id, TextType.SHORT)
    if description is None:
        myGroq = GroqLlama()
        description = myGroq.get_short_description(artwork, artist)
        
    labels_list = [label.strip() for label in labels.split(',')]
    
    digital_art_creator = ArtworkCreator(current_app.config['OPENAI_API_KEY'])
    image_urls, prompts = digital_art_creator.create_digital_art(labels_list, description, num_prompts=3, images_per_prompt=1)
    
    digital_art_files = []
    for i, (url, prompt) in enumerate(zip(image_urls, prompts)):
        image_content = digital_art_creator.get_image_content(url)
        if image_content:
            filename = f"digital_art_{i+1}.png"
            file = digital_art_creator.create_file_storage(image_content, filename)
            saved_filename, image_uri = save_art_file(file, art="ART", thisfilename=filename)
            if saved_filename:
                new_file = save_file_to_db(saved_filename, image_uri, current_user.id, False)
                created_art = save_created_art_to_db(
                    filename=saved_filename,
                    aws_url=image_uri,
                    user_id=current_user.id,
                    file_id=new_file.id,
                    is_random=True,  # You might want to add an option for this in the form
                    prompt=prompt,
                    art_id=art_id,
                    user_input=None  # There's no user input in this version
                )
                digital_art_files.append((saved_filename, image_uri,created_art.id))
    
    return render_template("digital_art.html", 
                           original_description=description, 
                           digital_art_files=digital_art_files, 
                           prompts=prompts)
    
    
    
    
    
    

@app.route('/uploads/<filename>')
def serve_image(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@app.route('/data/audio/<filename>')
def audio(filename):
    return send_from_directory(current_app.config['AUDIO_DIR'], filename)

@app.route('/video/<path:filename>')
def video(filename):
    return send_from_directory(current_app.config['VIDEO_DIR'], filename)

@app.route('/animation_status', methods=['GET'])
def animation_status_route():
    status = animation_status.get_status()
    return jsonify(status)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=0, debug=True)