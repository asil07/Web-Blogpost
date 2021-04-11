from flask import Flask, render_template, redirect, url_for, flash, request, g, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, backref
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import *
from flask_gravatar import Gravatar
from typing import Callable
from functools import wraps
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import os
Base = declarative_base()


class MySQLAlchemy(SQLAlchemy):
    Column: Callable
    Integer: Callable
    String: Callable
    Text: Callable


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

ckeditor = CKEditor(app)
Bootstrap(app)


# #CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = MySQLAlchemy(app)


# #CONFIGURE TABLES

class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password= db.Column(db.String(100))
    name = db.Column(db.String(1000))

    posts = relationship("BlogPost", back_populates="author")
    # shu yerda Parent relation qilindi Child bilan
    comments = relationship("Comment", back_populates="author")

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True, )

    # shu yerda author id qoshilgan
    author_id = db.Column(db.Integer, ForeignKey("user.id"))
    # author ni endi parent ga boglaymiz yani User() ga
    author = relationship("User", back_populates="posts")

    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    # shu yerda Parent relation qilindi Child bilan
    comments = relationship("Comment", back_populates="blog_post_comment")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, ForeignKey('user.id'))
    author = relationship("User", back_populates="comments")

    # Postning Id si Foreign key yordamida olindi
    post_id = db.Column(db.Integer, ForeignKey("blog_posts.id"))
    blog_post_comment = relationship("BlogPost", back_populates="comments")

    text = db.Column(db.String(500), nullable=False)
db.create_all()

login_manager = LoginManager()
login_manager.init_app(app)


def admin_only(function):
    @wraps(function)
    @login_required
    def decorated_function(*args, **kwargs):

        if current_user.id != 1:
            # flash("Siz admin emassiz")
            return abort(403)

        return function(*args, **kwargs)

    return decorated_function



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route("/register", methods=["POST", "GET"])
def register():
    form = RegisterForm()
    # if request.method == "POST":
    if form.validate_on_submit():
        if User.query.filter_by(email=request.form['email']).first():
            flash("Siz röyhatdan ötıb bölgansız, Accountingizga kirişıngız mümkün.")
            return redirect(url_for('login'))
        hashed_and_salted = generate_password_hash(request.form['password'],
                                                   method="pbkdf2:sha256", salt_length=8)
        new_user = User(email=request.form["email"],
                        password=hashed_and_salted,
                        name=request.form["name"]
                        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))
    return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()

    if form.validate_on_submit():

        email = request.form['email']
        user = User.query.filter_by(email=email).first() # shu yerga e'tibor
        password = request.form['password']
        if not User.query.filter_by(email=email).first():
            flash("Bunday email mavjud emas")
            return redirect(url_for('login'))
        if check_password_hash(user.password, password):  # shu yerda NoneType of object no attribute count

            login_user(user)

            return redirect(url_for('get_all_posts'))
        else:
            flash("Parolingiz no'to'g'ri")
            return redirect(url_for("login"))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment_form = CommentForm()
    gravatar = Gravatar(app,
                        size=100,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)
    if comment_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Login first")
            return redirect(url_for("login"))
        new_comment = Comment(text=comment_form.comment.data,
                              author=current_user,
                              blog_post_comment=requested_post
                              )

        db.session.add(new_comment)
        db.session.commit()
        return redirect(url_for("show_post", post_id=post_id, avatar=gravatar))
    return render_template("post.html", post=requested_post, form=comment_form,
                           current_user=current_user, avatar=gravatar)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():

    form = CreatePostForm()

    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author_id=current_user.id,
            date=date.today().strftime("%B %d, %Y")
            )
        print(new_post.body)
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    else:
        print("nopeeeeee")
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=current_user.name,
        body=post.body
    )

    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
