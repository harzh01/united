from flask import Flask, render_template, request, redirect, url_for, session, flash, Response
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from pymongo.server_api import ServerApi
import gridfs
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import os

app = Flask(__name__)
app.secret_key = "d5fb8c4fa8bd46638dadc4e751e0d68d"  
bcrypt = Bcrypt(app)


uri = "mongodb+srv://harzh0110:1hzrX4Iu7LLLFQEW@blog.n1wcn.mongodb.net/?retryWrites=true&w=majority&appName=blog"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)
db = client['blog_database']
users_collection = db['users']
posts_collection = db['posts']
comments_collection = db['comments']
fs = gridfs.GridFS(db)

# Allowed file extensions for profile pictures
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    posts = list(posts_collection.find())
    return render_template('index.html', posts=posts)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')

        if users_collection.find_one({'username': username}):
            flash('Username already exists!', 'danger')
            return redirect(url_for('signup'))

        users_collection.insert_one({'username': username, 'password': hashed_pw})
        flash('Signup successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = users_collection.find_one({'username': username})

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        user_id = session['user_id']
        posts = list(posts_collection.find({'user_id': user_id}))
        users = {user['_id']: user for user in users_collection.find()}  # Fetch all users

        # Add profile picture URLs to posts
        for post in posts:
            user = users.get(ObjectId(post['user_id']))
            post['profile_pic_id'] = user.get('profile_pic_id') if user else None

        return render_template('dashboard.html', posts=posts)

    flash('Please login to access the dashboard!', 'danger')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/post/new', methods=['GET', 'POST'])
def new_post():
    if 'user_id' not in session:
        flash('Please login to create a post!', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        user_id = session['user_id']

        posts_collection.insert_one({
            'title': title,
            'content': content,
            'user_id': user_id,
            'likes': 0,
            'dislikes': 0
        })
        flash('Post created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('new_post.html')

@app.route('/post/edit/<post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    if 'user_id' not in session:
        flash('Please login to edit a post!', 'danger')
        return redirect(url_for('login'))

    post = posts_collection.find_one({'_id': ObjectId(post_id), 'user_id': session['user_id']})

    if not post:
        flash('Post not found or unauthorized!', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        
        posts_collection.update_one({'_id': ObjectId(post_id)}, {'$set': {'title': title, 'content': content}})
        flash('Post updated successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('edit_post.html', post=post)

@app.route('/post/delete/<post_id>', methods=['POST'])
def delete_post(post_id):
    if 'user_id' not in session:
        flash('Please login to delete a post!', 'danger')
        return redirect(url_for('login'))

    user_id = session['user_id']
    post = posts_collection.find_one({'_id': ObjectId(post_id)})

    if post and post['user_id'] == user_id:
        posts_collection.delete_one({'_id': ObjectId(post_id)})
        flash('Post deleted successfully!', 'success')
    else:
        flash('Unauthorized action or post not found.', 'danger')

    return redirect(url_for('dashboard'))

@app.route('/post/<post_id>')
def post_details(post_id):
    post = posts_collection.find_one({'_id': ObjectId(post_id)})
    comments = comments_collection.find({'post_id': post_id})
    return render_template('post_details.html', post=post, comments=comments)

@app.route('/post/<post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user_id' not in session:
        flash('Please login to comment!', 'danger')
        return redirect(url_for('login'))

    content = request.form['content']
    comments_collection.insert_one({
        'post_id': post_id,
        'user_id': session['user_id'],
        'content': content
    })
    flash('Comment added successfully!', 'success')
    return redirect(url_for('post_details', post_id=post_id))

@app.route('/post/like/<post_id>', methods=['POST'])
def like_post(post_id):
    if 'user_id' not in session:
        flash('Please login to like a post!', 'danger')
        return redirect(url_for('login'))

    posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'likes': 1}})
    return redirect(url_for('index'))

@app.route('/post/dislike/<post_id>', methods=['POST'])
def dislike_post(post_id):
    if 'user_id' not in session:
        flash('Please login to dislike a post!', 'danger')
        return redirect(url_for('login'))

    posts_collection.update_one({'_id': ObjectId(post_id)}, {'$inc': {'dislikes': 1}})
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        flash('Please login to view your profile!', 'danger')
        return redirect(url_for('login'))

    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})

    if request.method == 'POST':
        username = request.form['username']
        profile_pic = request.files.get('profile_pic')

        if profile_pic:
            # Store the profile picture in GridFS
            fs = gridfs.GridFS(db)
            profile_pic_id = fs.put(profile_pic, filename=profile_pic.filename)
            users_collection.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': {'username': username, 'profile_pic_id': profile_pic_id}}
            )
        else:
            users_collection.update_one(
                {'_id': ObjectId(session['user_id'])},
                {'$set': {'username': username}}
            )
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', user=user)


@app.route('/profile_pic/<file_id>')
def profile_pic(file_id):
    file = fs.get(ObjectId(file_id))
    return Response(file.read(), mimetype=file.content_type)

if __name__ == '__main__':
    app.run(debug=True)
