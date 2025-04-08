# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_login import login_user, logout_user, current_user
# 假设你的 User 模型和 db 实例在 'models.py' 中定义
from models import db, User
# 导入 LoginManager (虽然在这个片段中没有直接配置它，但它通常是 Flask-Login 设置的一部分)
# from flask_login import LoginManager

# --- 重要前提 ---
# 1. 你的 Flask app 必须配置了一个 `SECRET_KEY`。这是用来签名 session cookie 的，确保其不被篡改。
#    app.config['SECRET_KEY'] = '你的强随机密钥'
# 2. 你的 User 模型必须正确继承自 flask_login.UserMixin 并实现了必要的方法/属性，
#    特别是 `get_id()`。
# 3. 你的 User 模型应该有安全的密码处理方法，例如 `set_password(password)` (哈希密码)
#    和 `verify_password(password)` (验证哈希)。下面的代码假设这些方法存在。
# 4. LoginManager 需要被初始化并配置 `login_view` 和 `user_loader`。
#    login_manager = LoginManager()
#    login_manager.init_app(app)
#    login_manager.login_view = 'login' # 或者你的登录路由名
#    @login_manager.user_loader
#    def load_user(user_id):
#        return User.query.get(int(user_id))
# --- 前提结束 ---

def register_user_routes(app: Flask):
    """
    注册用户相关的 Flask 路由。

    Args:
        app: Flask 应用实例。
    """

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """
        处理用户注册请求。
        GET: 显示注册表单。
        POST: 处理注册逻辑。
        """
        # 如果用户已经通过认证 (即 session cookie 有效且包含用户 ID)，则重定向到主页
        if current_user.is_authenticated:
            # 假设你的主页路由名为 'index'
            return redirect(url_for('index'))

        if request.method == 'POST':
            # 从 POST 请求的表单中获取数据
            username = request.form.get('username') # 使用 .get() 更安全
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # --- 输入验证 ---
            if not username or not password or not confirm_password:
                flash('所有字段均为必填项', 'danger')
                return render_template('register.html', current_user=current_user, username=username) # 保留已输入的用户名

            if password != confirm_password:
                flash('两次输入的密码不一致', 'danger')
                # 将错误信息传递给模板，以便在页面上显示
                return render_template('register.html', error="两次输入的密码不一致", current_user=current_user, username=username)

            # 检查用户名是否已经存在于数据库中
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash('该用户名已被注册，请选择其他用户名', 'danger')
                # 将错误信息传递给模板
                return render_template('register.html', error="该用户名已被注册", current_user=current_user, username=username)
            # --- 验证结束 ---

            # --- 创建新用户 ---
            try:
                # 创建 User 对象实例
                # 重要：密码绝不应明文存储！User 模型应负责哈希密码。
                new_user = User(username=username)
                # 假设 User 模型有一个 set_password 方法来哈希密码
                new_user.set_password(password)

                # 将新用户添加到数据库会话
                db.session.add(new_user)
                # 提交事务，将用户数据保存到数据库
                db.session.commit()

                flash('注册成功，现在您可以登录了!', 'success')
                # 注册成功后，重定向到登录页面
                # 如果使用了 Blueprint，可能需要像 'auth.login' 这样指定
                return redirect(url_for('login'))

            except Exception as e:
                # 如果在数据库操作中发生错误，回滚事务
                db.session.rollback()
                app.logger.error(f"注册用户 {username} 时出错: {e}") # 记录错误日志
                flash(f'注册过程中发生错误，请稍后重试。错误: {e}', 'danger')
                return render_template('register.html', error="注册失败", current_user=current_user, username=username)
            # --- 创建结束 ---

        # 如果是 GET 请求，或者 POST 请求验证失败后重新渲染页面
        return render_template('register.html', current_user=current_user)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """
        处理用户登录请求。
        GET: 显示登录表单。
        POST: 处理登录逻辑，验证用户凭据，并在成功时设置 session cookie。
        """
        # 如果用户已经通过认证，则重定向到主页
        if current_user.is_authenticated:
            return redirect(url_for('index'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')

            if not username or not password:
                flash('请输入用户名和密码', 'danger')
                return render_template('login.html', current_user=current_user, username=username)

            # 在数据库中查找用户
            user = User.query.filter_by(username=username).first()

            # 验证用户是否存在，以及密码是否正确
            # 假设 User 模型有一个 verify_password 方法来比较输入密码和存储的哈希
            if user and user.verify_password(password):
                # --- 登录成功 ---
                # 使用 Flask-Login 的 login_user 函数
                # 这个函数会做几件事：
                # 1. 将用户的 ID 存储在 Flask 的 session 中。
                # 2. Flask 会自动将 session 数据序列化、签名（使用 SECRET_KEY），
                #    然后通过 Set-Cookie HTTP 响应头发送给客户端（浏览器或 App）。
                # 3. 客户端（如 Android App 的 HTTP 库）需要配置为存储这个 cookie
                #    并在后续请求中自动带上它。
                # 4. remember=True 会让 cookie 成为持久性 cookie（有较长过期时间），
                #    否则它是一个会话 cookie（浏览器关闭时通常会删除）。
                login_user(user, remember=True) # 可以根据需要设置 remember=True/False

                # !!! 关键点：不要手动将 SECRET_KEY 放入 session !!!
                # 下面这行代码是 **错误且危险** 的，已经移除：
                # session['secret_key'] = app.config['SECRET_KEY']
                # SECRET_KEY 仅用于服务器端签名 cookie，绝不能发送给客户端。

                flash('登录成功!', 'success')

                # 尝试获取登录前用户想访问的页面 (Flask-Login 会自动处理 ?next=URL)
                next_page = request.args.get('next')
                # 如果没有 next 参数，则重定向到主页 'index'
                # 如果有 next 参数，但它不是一个安全的 URL (例如，指向外部网站)，
                # url_for('index') 提供了安全的回退。
                # (更安全的做法是验证 next_page 是否是应用内的相对路径)
                return redirect(next_page or url_for('index'))
                # --- 登录成功结束 ---
            else:
                # --- 登录失败 ---
                flash('用户名或密码无效，请重试', 'danger')
                # 将错误信息传递给模板
                return render_template('login.html', error="用户名或密码无效", current_user=current_user, username=username)

        # 如果是 GET 请求，或者 POST 请求验证失败后重新渲染页面
        return render_template('login.html', current_user=current_user)

    @app.route('/logout')
    # @login_required # 通常需要用户登录后才能登出，可以添加此装饰器
    def logout():
        """
        处理用户登出请求。
        清除 session 中的用户认证信息，使 session cookie 失效。
        """
        # 使用 Flask-Login 的 logout_user 函数
        # 这个函数会从 session 中移除用户 ID 等认证信息。
        # Flask 在下次响应时，可能会发送一个更新后的、不包含用户信息的 session cookie，
        # 或者发送一个指令来清除客户端的 session cookie (取决于 Flask 配置和版本)。
        # 效果是让客户端后续请求不再被认证为该用户。
        logout_user()

        flash('您已成功登出。', 'info')
        # 登出后通常重定向到登录页面
        return redirect(url_for('login'))

# --- Android App 集成要点 ---
# 1.  **HTTP 客户端配置**: Android App 中的 HTTP 请求库 (如 OkHttp, Volley, Retrofit) 必须配置为能够处理 Cookie。
#     *   对于 OkHttp: 需要设置一个 `CookieJar` (例如 `JavaNetCookieJar` 或自定义实现)。
#     *   对于 Volley: 通常需要确保底层的 HTTP stack (如 HurlStack) 支持 Cookie，或者手动管理 Cookie 头。
# 2.  **登录请求**: App 发送 POST 请求到 `/login`，包含用户名和密码。
# 3.  **Cookie 存储**: App 的 HTTP 客户端在收到 `/login` 成功响应时，会自动（如果配置正确）或手动提取 `Set-Cookie` 响应头中的 `session` cookie 并存储起来。
# 4.  **后续请求**: 对于需要认证的 API 接口（例如获取用户资料 `/profile`），App 发送请求时，其 HTTP 客户端会自动（如果配置正确）在请求头中添加 `Cookie: session=...`。
# 5.  **服务器验证**: Flask 服务器收到带有 `session` cookie 的请求后，会验证签名，然后 Flask-Login 的 `user_loader` 会根据 cookie 中的用户 ID 加载 `current_user`。这样，受 `@login_required` 保护的路由就能正常工作。
# 6.  **登出请求**: App 发送 GET 请求到 `/logout`。
# 7.  **Cookie 清除**: 服务器响应 `/logout` 时，`logout_user()` 会使 session 无效。客户端的 `CookieJar` 应该能处理服务器发出的清除 cookie 的指令（例如，设置过期时间为过去）。
# 8.  **安全性**: 务必使用 HTTPS 来保护 Cookie 在传输过程中不被窃听。Flask 的 session cookie 是签名的，能防止篡改，但不能防止窃听。