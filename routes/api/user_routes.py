from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, current_user
from models import db, User

def register_user_routes(app):
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            confirm_password = request.form['confirm_password']
            if password != confirm_password:
                flash('两次密码输入不一致', 'danger')
                return render_template('register.html', error="两次密码输入不一致", current_user=current_user)
            if User.query.filter_by(username=username).first():
                flash('用户名已存在', 'danger')
                return render_template('register.html', error="用户名已存在", current_user=current_user)

            new_user = User(username=username, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('注册成功，请登录', 'success')
            return redirect(url_for('login'))
        return render_template('register.html', current_user=current_user)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for('index'))
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and user.verify_password(password):
                login_user(user)
                session['secret_key'] = app.config['SECRET_KEY']  # 将 secret_key 存储在 session 中
                flash('登录成功!', 'success')
                return redirect(url_for('index'))
            else:
                flash('用户名或密码错误', 'danger')
                return render_template('login.html', error="用户名或密码错误", current_user=current_user)
        return render_template('login.html', current_user=current_user)

    @app.route('/logout')
    def logout():
        logout_user()
        flash('您已登出', 'info')
        return redirect(url_for('login'))