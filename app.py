import os
import numpy as np
from PIL import Image
from flask import Flask, render_template, url_for, redirect, request, jsonify
from flask_bcrypt import Bcrypt
from flask_login import UserMixin, login_user, LoginManager, logout_user, login_required
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms.fields.simple import StringField, SubmitField, FileField, PasswordField
from wtforms.validators import InputRequired, Length, ValidationError
import tensorflow as tf
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Configuration using environment variables
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['UPLOAD_FOLDER'] = os.getenv('UPLOAD_FOLDER')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Load the model
model_path = os.getenv('MODEL_PATH')
loaded_model = tf.keras.models.load_model(model_path)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Database model for User
class User(db.Model, UserMixin):
    __tablename__ = 'registered_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)],
                           render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)],
                             render_kw={"placeholder": "Password"})
    submit = SubmitField("Register")

    def validate_username(self, username):
        existing_user = User.query.filter_by(username=username.data).first()
        if existing_user:
            raise ValidationError("This username already exists. Please choose a different one.")


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=4, max=20)],
                           render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=4, max=20)],
                             render_kw={"placeholder": "Password"})
    submit = SubmitField("Login")


class UploadForm(FlaskForm):
    image = FileField(validators=[InputRequired()])
    submit = SubmitField("Upload")


@app.route('/')
def home():
    return render_template('home.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    result = None  
    message = ''
    if request.method == 'POST':
        if 'image' not in request.files:
            message = 'No file part'
        else:
            file = request.files['image']
            if file.filename == '':
                message = 'No selected file'
            else:
                print("Received image:", file.filename)
                imgo = Image.open(file)
                img_array = load_and_preprocess_image(imgo)
                print("Image array shape:", img_array.shape)

                # Model prediction
                prediction_result = loaded_model.predict(img_array)
                pa = 1 - float(prediction_result)
                pas = "{:.2f}".format(pa)
                pn = float(prediction_result)
                pns = "{:.2f}".format(pn)

                result = f"Autistic: {pas}% <br> Non Autistic: {pns}%"
                print("Prediction result:", result)

                message = 'File uploaded successfully'
                return jsonify({'result': result, 'message': message})

    return render_template('dashboard.html')

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for('welcome'))
    return render_template('login.html', form=form)

@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        new_user = User(username=form.username.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/dashboard_2', methods=['GET', 'POST'])
@login_required
def dashboard_2():
    image_dir = app.config['UPLOAD_FOLDER']
    images = os.listdir(image_dir)

    class_0_images = []
    class_1_images = []

    if request.method == 'POST':
        delete_items(image_dir)
        uploaded_files = request.files.getlist('images[]')
        print("Uploaded files:", uploaded_files)

        for file in uploaded_files:
            filename = file.filename
            file_path = os.path.join(image_dir, filename)
            file.save(file_path)

            # Load and preprocess image
            with Image.open(file_path) as img:
                img_array = load_and_preprocess_image(img)
                print("Image shape:", img_array.shape)

            # Predict using the model
            prediction_result = loaded_model.predict(img_array)
            print("Prediction result:", prediction_result)

            # Classify images
            if prediction_result > 0.3:
                class_0_images.append(filename)
            else:
                class_1_images.append(filename)

        print("Class 0 Images:", class_0_images)
        print("Class 1 Images:", class_1_images)

        return jsonify({'class_0_images': class_0_images, 'class_1_images': class_1_images})

    return render_template('dashboard_2.html', images=images)

def delete_items(directory):
    """Delete all files in the given directory."""
    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)
        os.remove(item_path)

def load_and_preprocess_image(img):
    """Resize, normalize, and expand dimensions of an image for model prediction."""
    img_resized = img.resize((224, 224))
    img_array = np.array(img_resized) / 255.0
    return np.expand_dims(img_array, axis=0)

if __name__ == '__main__':
    app.run(debug=True)
