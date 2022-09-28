# Playground for learning SQL injection
# Copyright (C) 2022 KizhiFox (https://github.com/KizhiFox)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sqlite3
import hashlib
import base64
from pathlib import Path
from urllib.parse import urlparse, unquote, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer


SQLITE_FILENAME = 'sql_injection.db'
PORT = 8080


class SQLServer(BaseHTTPRequestHandler):
    def _wrap_html(self, body: str) -> str:
        return f'''<!DOCTYPE html>
        <html>
            <body>
                <div>
                    <a href="/">Главная страница</a> | 
                    <a href="/users">Список пользователей</a> | 
                    <a href="/my-profile">Вход</a> | 
                    <a href="/register">Регистрация</a>
                </div>
                {body}
            </body>
        </html>'''

    def do_GET(self):
        url_path = urlparse(unquote(self.path))
        path = [p for p in url_path.path.split('/') if p != '']
        if not path:
            path.append('')

        # Main page with instructions
        if path[0] == '' and len(path) == 1:
            with open('instructions.html', 'r', encoding='utf8') as f:
                response = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # Get registration form
        elif path[0] == 'register' and len(path) == 1:
            response = '''
                <form action="/register-result" method="post">
                    <label for="nickname">Логин:</label><br>
                    <input type="text" id="nickname" name="nickname"><br>
                    <label for="password">Пароль:</label><br>
                    <input type="text" id="password" name="password"><br><br>
                    <label for="name">Имя:</label><br>
                    <input type="text" id="name" name="name"><br>
                    <label for="surname">Фамилия:</label><br>
                    <input type="text" id="surname" name="surname"><br>
                    <label for="group_num">Номер группы:</label><br>
                    <input type="text" id="group_num" name="group_num"><br>
                    <label for="status">Статус:</label><br>
                    <input type="text" id="status" name="status"><br>
                    <input type="submit" value="Зарегистрироваться">
                </form>
            '''
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # Get all users
        elif path[0] == 'users' and len(path) == 1:
            con = sqlite3.connect(SQLITE_FILENAME)
            cur = con.cursor()
            try:
                cur.execute(f"SELECT nickname, status FROM users")
                users = cur.fetchall()

                response = ''
                for user in users:
                    user_name = user[0]
                    user_status = user[1]
                    response += f'''<table style="text-align:left;">
                                <tr><th><div style="width:100px;height:100px;border-radius:50px;background-color:blue;color:white;vertical-align:middle;text-align:center;font-size: 80px;">{user_name[0]}</div></th>
                                <th><h2><a href="/users/{user_name}">{user_name}</a></h2><p>{user_status}</p></th></tr></table>\n'''

                if response == '':
                    self.send_response(200)
                    response = '<h1>Здесь пока никто не зарегистрировался</h1>'
                else:
                    self.send_response(200)

            except Exception as e:
                self.send_response(500)
                response = f"<p>SELECT nickname, status FROM users</p>\n<p>{e}</p>"

            finally:
                con.close()

            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # Get user
        # Hack: /users/' OR 1=1 UNION SELECT nickname, name from users UNION SELECT nickname, surname from users UNION SELECT nickname, pwd_hash from users UNION SELECT nickname, group_num from users--
        elif path[0] == 'users' and len(path) == 2:

            nickname = path[1]

            con = sqlite3.connect(SQLITE_FILENAME)
            cur = con.cursor()
            try:
                cur.execute(f"SELECT nickname, status FROM users WHERE nickname = '{nickname}'")
                users = cur.fetchall()

                response = ''
                for user in users:
                    user_name = user[0]
                    user_status = user[1]
                    response += f'''<table style="text-align:left;">
                                <tr><th><div style="width:100px;height:100px;border-radius:50px;background-color:blue;color:white;vertical-align:middle;text-align:center;font-size: 80px;">{user_name[0]}</div></th>
                                <th><h2>{user_name}</h2><p>{user_status}</p></th></tr></table>\n'''

                if response == '':
                    self.send_response(404)
                    response = '<h1>Этот пользователь не существует</h1>'
                else:
                    self.send_response(200)

            except Exception as e:
                self.send_response(500)
                response = f"<p>SELECT nickname, status FROM users WHERE nickname = '{nickname}'</p>\n<p>{e}</p>"

            finally:
                con.close()

            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # Get full user profile
        elif path[0] == 'my-profile' and len(path) == 1:
            # Check header
            if self.headers.get('Authorization') is None:
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = f'''
                    <input type="text" id="login" name="login" placeholder="Логин"><br>
                    <input type="text" id="password" name="password" placeholder="Пароль"><br>
                    <button onclick="auth()">Войти</button>
                    <script>
                        function auth() {{
                            var credentials = btoa(`${{document.getElementById('login').value}}:${{document.getElementById('password').value}}`);
                            let xhr = new XMLHttpRequest();
                            xhr.onreadystatechange = function () {{
                                if (xhr.readyState == 4) {{
                                    var new_window = window.open('', '_self');
                                    new_window.location.href='/my-profile'
                                    new_window.document.write(xhr.responseText);
                                }}
                            }}
                            xhr.open('get', '/my-profile', true); 
                            xhr.setRequestHeader('Content-Type', 'text/html; charset=utf-8');
                            xhr.setRequestHeader('Authorization', `Basic ${{credentials}}`);
                            xhr.send();
                        }}
                    </script>
                '''
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return
            if self.headers.get('Authorization').split(' ')[0] != 'Basic':
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = f'<h1>Неправильный метод авторизации</h1>'
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            # Get login and password
            try:
                nickname, password = base64.b64decode(self.headers.get('Authorization')[6:]).decode('utf8').split(':')
            except ValueError:
                self.send_response(403)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = '<h1>Неправильное имя пользователя или пароль</h1>'
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            # Check nulls
            if None in [nickname, password]:
                self.send_response(403)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = '<h1>Неправильное имя пользователя или пароль</h1>'
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            con = sqlite3.connect(SQLITE_FILENAME)
            cur = con.cursor()
            try:
                cur.execute(f"SELECT nickname, name, surname, group_num, status, pwd_hash FROM users WHERE nickname = '{nickname}'")
                users = cur.fetchall()

                # Check login and password
                if len(users) == 0:
                    self.send_response(403)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    response = f'<h1>Неправильное имя пользователя или пароль</h1>'
                    self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                    return
                if nickname != users[0][0] or hashlib.sha256(password.encode('utf8')).hexdigest().upper() != users[0][5]:
                    self.send_response(403)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    response = f'<h1>Неправильное имя пользователя или пароль</h1>'
                    self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                    return

                # Show user's page
                response = f'''
                    <table style="text-align:left;">
                        <tr><th><div style="width:100px;height:100px;border-radius:50px;background-color:blue;color:white;vertical-align:middle;text-align:center;font-size: 80px;">{users[0][0][0]}</div></th>
                        <th>
                            <h2>{users[0][0]}</h2>
                            <div>Имя: {users[0][1]}</div>
                            <div>Фамилия: {users[0][2]}</div>
                            <div>Статус: {users[0][4]}</div>
                            <div>Номер группы: {users[0][3]}</div>
                        </th></tr>
                    </table>
                '''

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = f"<p>SELECT nickname, name, surname, group_num, status, pwd_hash FROM users WHERE nickname = '{nickname}'</p>\n<p>{e}</p>"
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            finally:
                con.close()

            # Send page
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # 404
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            response = '<h1>ERROR 404: Page not found</h1>'
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

    def do_POST(self):
        url_path = urlparse(unquote(self.path))
        path = [p for p in url_path.path.split('/') if p != '']
        if not path:
            path.append('')

        # Get registration form
        if path[0] == 'register-result' and len(path) == 1:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf8')
            data = parse_qs(post_data)
            nickname = data['nickname'][0] if 'nickname' in data else None
            name = data['name'][0] if 'name' in data else None
            surname = data['surname'][0] if 'surname' in data else None
            group_num = data['group_num'][0] if 'group_num' in data else None
            status = data['status'][0] if 'status' in data else None
            password = data['password'][0] if 'password' in data else None

            # Check nulls
            if None in [nickname, name, surname, group_num, status, password]:
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = '<h1>Заполните все поля!</h1><br><a href="javascript:history.back()">Назад к регистрации</a>'
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            # Check user exists
            con = sqlite3.connect(SQLITE_FILENAME)
            cur = con.cursor()
            try:
                cur.execute(f"SELECT nickname FROM users WHERE nickname = '{nickname}'")
                users = cur.fetchall()

                if len(users) > 0:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    response = f'<h1>Пользователь с ником {nickname} уже существует</h1><br><a href="javascript:history.back()">Назад к регистрации</a>'
                    self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                    return

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = f"<p>SELECT nickname FROM users WHERE nickname = '{nickname}'</p>\n<p>{e}</p>"
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            finally:
                con.close()

            # Register new user
            pwd_hash = hashlib.sha256(password.encode('utf8')).hexdigest().upper()
            con = sqlite3.connect(SQLITE_FILENAME)
            cur = con.cursor()
            try:
                cur.execute(f"INSERT INTO users VALUES ('{nickname}', '{name}', '{surname}', '{group_num}', '{status}', '{pwd_hash}')")
                con.commit()

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                response = f"<p>INSERT INTO users VALUES ('{nickname}', '{name}', '{surname}', '{group_num}', '{status}', '{pwd_hash}')</p>\n<p>{e}</p>"
                self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))
                return

            finally:
                con.close()

            response = f'<h1>Поздравляем с регистрацией!</h1><br>'
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

        # 404
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            response = '<h1>ERROR 404: Page not found</h1>'
            self.wfile.write(self._wrap_html(response).encode(encoding='utf8'))

def run():
    # Init new SQLite DB (delete sql_injection.db to delete all data)
    if not Path(SQLITE_FILENAME).exists():
        print('Creating new table')
        con = sqlite3.connect(SQLITE_FILENAME)
        cur = con.cursor()
        cur.execute('CREATE TABLE users (nickname text, name text, surname text, group_num text, status text, pwd_hash text)')
        con.commit()
        con.close()

    # Run server
    server = HTTPServer(('', PORT), SQLServer)
    print(f'Serving at {"http"}://{"localhost"}:{PORT}')
    server.serve_forever()


if __name__ == '__main__':
    run()
