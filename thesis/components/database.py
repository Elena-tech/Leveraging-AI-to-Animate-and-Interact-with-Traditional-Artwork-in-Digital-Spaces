from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from flask_login import UserMixin
from components.groq_llama import ArtworkInfo
from flask_migrate import Migrate, upgrade
from typing import List, Dict
from config import MediaType, TextType

db = SQLAlchemy()

class ArtQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    art_id = db.Column(db.Integer, db.ForeignKey('art.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    art = db.relationship('Art', backref=db.backref('questions', lazy=True))
    user = db.relationship('User', backref=db.backref('art_questions', lazy=True))

class ArtContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    art_id = db.Column(db.Integer, db.ForeignKey('art.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # 'text', 'audio', 'video'
    content_url = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    art = db.relationship('Art', backref=db.backref('contents', lazy=True))

class ArtUserContent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    art_id = db.Column(db.Integer, db.ForeignKey('art.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # 'short', 'style', 'long'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    art = db.relationship('Art', backref=db.backref('user_comments', lazy=True))
    user = db.relationship('User', backref=db.backref('art_comments', lazy=True))


class ArtText(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    art_id = db.Column(db.Integer, db.ForeignKey('art.id'), nullable=False)
    content_type = db.Column(db.String(20), nullable=False)  # 'short', 'style', 'long'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    art = db.relationship('Art', backref=db.backref('text_contents', lazy=True))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    files = db.relationship('File', backref='user', lazy=True)
    arts = db.relationship('Art', backref='user', lazy=True)
    createdarts = db.relationship('CreatedArt', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_id(self):
        return str(self.id)

class File(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    aws_url = db.Column(db.String(200), nullable=False)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_user_upload = db.Column(db.Boolean, nullable=False, default=True)

class Art(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    painter_name = db.Column(db.String(100), nullable=False)
    art_name = db.Column(db.String(200), nullable=False)
    is_portrait = db.Column(db.Boolean, nullable=False, default=True)
    gender = db.Column(db.String(20), nullable=True)  
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)

class CreatedArt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    aws_url = db.Column(db.String(200), nullable=False)
    is_random = db.Column(db.Boolean, nullable=False, default=False)
    prompt = db.Column(db.Text, nullable=False)
    user_input = db.Column(db.Text, nullable=True)
    upload_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    art_id = db.Column(db.Integer, db.ForeignKey('art.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False)   

class ArtManager:
    @staticmethod
    def copy_art_for_user(art: Art, user_id: int) -> Art:
        new_art = Art(
            painter_name=art.painter_name,
            art_name=art.art_name,
            is_portrait=art.is_portrait,
            gender=art.gender,
            user_id=user_id,
            file_id=art.file_id
        )
        db.session.add(new_art)
        db.session.flush()  # This assigns an ID to new_art

        ArtManager.copy_art_content(art.id, new_art.id, user_id)
        
        db.session.commit()
        return new_art

    @staticmethod
    def copy_art_content(old_art_id: int, new_art_id: int, user_id: int):
        # Copy all ArtText entries
        old_texts = ArtText.query.filter_by(art_id=old_art_id).all()
        for text in old_texts:
            new_text = ArtText(
                art_id=new_art_id,
                user_id=user_id,
                content_type=text.content_type,
                content=text.content
            )
            db.session.add(new_text)

        old_contents = ArtContent.query.filter_by(art_id=old_art_id).all()
        for content in old_contents:
            new_content = ArtContent(
                art_id=new_art_id,
                content_type=content.content_type,
                content_url=content.content_url
            )
            db.session.add(new_content)

    @staticmethod
    def get_artwork_full_info(art_id: int) -> ArtworkInfo:
        texts = ArtText.query.filter_by(art_id=art_id).all()
        contents = ArtContent.query.filter_by(art_id=art_id).all()

        text_dict = {TextType(text.content_type): text.content for text in texts}
        content_dict = {MediaType(content.content_type): content.content_url for content in contents}

        return ArtworkInfo(
            labels=text_dict.get(TextType.LABELS, ''),
            short_description=text_dict.get(TextType.SHORT, ''),
            style_description=text_dict.get(TextType.STYLE, ''),
            long_description=text_dict.get(TextType.LONG, ''),
            audio_file=content_dict.get(MediaType.AUDIO, ''),
            intro_audio_file=content_dict.get(MediaType.INTRO_AUDIO, ''),
            video_file=content_dict.get(MediaType.VIDEO, ''),
            intro_story=text_dict.get(TextType.INTRO, '')
        )

    @staticmethod
    def ensure_art_content(art: Art, artwork_info: ArtworkInfo):
        for text_type, content in {
            TextType.LABELS: artwork_info['labels'],
            TextType.SHORT: artwork_info['short_description'],
            TextType.STYLE: artwork_info['style_description'],
            TextType.LONG: artwork_info['long_description'],
            TextType.INTRO: artwork_info['intro_story']
        }.items():
            if content and not ArtText.query.filter_by(art_id=art.id, content_type=text_type.value).first():
                DatabaseManager.add_art_text(art.id, content, text_type)

        for media_type, content_url in {
            MediaType.AUDIO: artwork_info['audio_file'],
            MediaType.INTRO_AUDIO: artwork_info['intro_audio_file'],
            MediaType.VIDEO: artwork_info['video_file']
        }.items():
            if content_url and not ArtContent.query.filter_by(art_id=art.id, content_type=media_type.value).first():
                DatabaseManager.add_art_content(art.id, media_type, content_url)

class DatabaseManager:
    @staticmethod
    def init_app(app):
        db.init_app(app)
        Migrate(app, db)

    @staticmethod
    def init_database(app):
        with app.app_context():
            db.create_all()
            print("Database tables created.")

    @staticmethod
    def database_exists():
        engine = db.engine
        inspector = db.inspect(engine)
        return len(inspector.get_table_names()) > 0

    @staticmethod
    def create_tables():
        db.create_all()

    @staticmethod
    def add_user(username, email, password):
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def get_user_by_username(username):
        return User.query.filter_by(username=username).first()

    @staticmethod
    def add_file(filename, aws_url, user_id, is_user_upload):
        file = File(filename=filename, aws_url=aws_url, user_id=user_id,is_user_upload=is_user_upload)
        db.session.add(file)
        db.session.commit()
        return file

    @staticmethod
    def get_files_by_user(user_id, is_user_upload=None):
        query = File.query.filter_by(user_id=user_id)
        print(query.all())
        if is_user_upload is not None:
            query = query.filter_by(is_user_upload=is_user_upload)
        print(query.all())
        return query.all()

    @staticmethod
    def get_file_by_id(file_id):
        return File.query.get(file_id)

    @staticmethod
    def get_user_by_id(user_id):
        return User.query.get(int(user_id))

    @staticmethod
    def save_art_to_db(artwork_info: ArtworkInfo, user_id: int, file_id: int):
        new_art = Art(
            painter_name=artwork_info['PainterName'],
            art_name=artwork_info['Artwork'],
            is_portrait=artwork_info['HasPerson'],
            gender=artwork_info['PersonGender'],
            user_id=user_id,
            file_id=file_id
        )
        db.session.add(new_art)
        db.session.commit()
        return new_art

    @staticmethod
    def add_new_model_and_migrate(app):
        with app.app_context():
            db.create_all()
        print("New model added and database updated.")

    @staticmethod
    def save_created_art_to_db(filename: str, aws_url: str, user_id: int, file_id: int, 
                       is_random: bool, prompt: str, art_id: int, user_input: str = None) -> 'CreatedArt':
        new_art = CreatedArt(
            filename=filename,
            aws_url=aws_url,
            user_id=user_id,
            file_id=file_id,
            is_random=is_random,
            prompt=prompt,
            user_input=user_input,
            art_id=art_id
        )
        db.session.add(new_art)
        db.session.commit()
        return new_art

    @staticmethod
    def get_user_art(user_id: int) -> List['CreatedArt']:
        return CreatedArt.query.filter_by(user_id=user_id).all()
    
    @staticmethod
    def add_art_content(art_id, content_type, content_url):
        content = ArtContent(art_id=art_id, content_type=content_type.value, 
                             content_url=content_url)
        db.session.add(content)
        db.session.commit()
        return content

    @staticmethod
    def add_art_text(art_id, content, content_type):
        art_text = ArtText(art_id=art_id, content=content, content_type=content_type.value)
        db.session.add(art_text)
        db.session.commit()
        return art_text

    @staticmethod
    def get_art_comments(art_id):
        return ArtText.query.filter_by(art_id=art_id).all()
    
    @staticmethod
    def get_existing_art(artist: str, artwork: str) -> Art:
        return Art.query.filter_by(painter_name=artist, art_name=artwork).first()
    
    @staticmethod
    def get_art_by_file_id(file_id: int) -> Art:
        return Art.query.filter_by(file_id=file_id).first()
    
    @staticmethod
    def get_art_by_user_and_file(user_id:int,file_id: int) -> Art:
        return Art.query.filter_by(user_id=user_id,file_id=file_id).first()
    
    @staticmethod
    def add_art_question(art_id: int, user_id: int, question: str) -> ArtQuestion:
        new_question = ArtQuestion(art_id=art_id, user_id=user_id, question=question)
        db.session.add(new_question)
        db.session.commit()
        return new_question
    
    @staticmethod
    def add_art_user_content(art_id: int, user_id: int, content, content_type) -> ArtUserContent:
        new_art_user_content = ArtUserContent(art_id=art_id, user_id=user_id, content=content, content_type=content_type.value)
        db.session.add(new_art_user_content)
        db.session.commit()
        return new_art_user_content

    @staticmethod
    def update_art_question_answer(question_id: int, answer: str) -> ArtQuestion:
        question = ArtQuestion.query.get(question_id)
        if question:
            question.answer = answer
            question.updated_at = datetime.utcnow()
            db.session.commit()
        return question

    @staticmethod
    def get_art_questions(art_id: int, user_id: int) -> List[ArtQuestion]:
        return ArtQuestion.query.filter_by(art_id=art_id, user_id=user_id).all()
    
    @staticmethod
    def video_exists_for_art(art_id: int):
        return ArtContent.query.filter_by(art_id=art_id, content_type=MediaType.VIDEO.value).first()
    
    @staticmethod
    def get_art_text(art_id: int, text_type: str):
        art_text = ArtText.query.filter_by(art_id=art_id, content_type=text_type.value).first()
        return art_text.content if art_text else None
    
    @staticmethod
    def get_art_content(art_id: int, media_type: str):
        art_content = ArtContent.query.filter_by(art_id=art_id, content_type=media_type.value).first()
        print(art_content)
        return art_content.content_url if art_content else None
    
    @staticmethod
    def get_art_texts(art_id: int) -> Dict[TextType, str]:
        texts = ArtText.query.filter_by(art_id=art_id).all()
        return {TextType(text.content_type): text.content for text in texts}

    @staticmethod
    def get_art_contents(art_id: int) -> Dict[MediaType, str]:
        contents = ArtContent.query.filter_by(art_id=art_id).all()
        return {MediaType(content.content_type): content.content_url for content in contents}