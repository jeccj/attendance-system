# 简易课堂签到系统

一个从零编写的课堂签到项目，适合软件工程课程实验和小规模演示。

使用 **Python + Flask + SQLite**。页面使用 HTML、CSS 和少量原生 JavaScript，不需要 Node.js、MySQL 或前端构建工具。

## 功能

- 教师登录，填写课程名称、签到主题和有效时长，生成 6 位签到码。
- 学生填写签到码、学号和姓名，完成签到后查看回执，无需注册账号。
- 同一次签到中，同一学号只能提交一次；到期自动停止接收，也可提前结束。
- 教师查看签到人数、历史签到和明细，导出带中文表头的 CSV 文件。
- 数据自动保存在本地，关闭程序后不会丢失。

## 快速运行

推荐使用 Python 3.12，首次运行会自动创建数据库。

在解压后的 `attendance-system` 文件夹打开终端：

```powershell
python -m pip install -r requirements.txt
python app.py
```

然后打开 **http://127.0.0.1:5000**。

| 入口 | 地址 |
| --- | --- |
| 学生签到 | http://127.0.0.1:5000/ |
| 教师登录 | http://127.0.0.1:5000/teacher/login |
| 教师工作台 | http://127.0.0.1:5000/teacher |

初始教师账号：**admin**；初始密码：**admin123**。这是课程演示用账号。

### 使用虚拟环境（可选）

Windows PowerShell，无需激活虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Ubuntu / Debian：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

## 一次完整演示

1. 打开教师登录页，用 `admin / admin123` 登录。
2. 在工作台填写“软件工程”“实验一课堂签到”，选择 10 分钟，点击“生成签到码”。
3. 复制生成的签到码，打开学生签到页；需要同时演示不同用户时可使用另一个浏览器或隐身窗口。
4. 输入签到码、学号（例如 `20240001`）和姓名，点击“确认签到”。
5. 回到教师页面，点击“刷新”，查看记录；点击“导出 CSV”下载表格。
6. 点击“提前结束签到”，之后该签到码将无法继续使用。

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `app.py` | 路由、教师登录、签到校验、数据库访问与 CSV 导出 |
| `schema.sql` | 三张表：教师、签到活动、签到记录 |
| `templates/` | 学生签到、教师工作台、记录详情等页面 |
| `static/style.css` | 页面样式和手机适配 |
| `static/app.js` | 复制签到码、提交反馈与结束确认 |
| `requirements.txt` | Python 依赖 |
| `tests/test_app.py` | 核心流程的集成测试 |

运行后会生成 `instance/attendance.db` 和 `instance/secret.key`。数据库保存记录，密钥用于签名登录会话。它们已被 `.gitignore` 排除，不要上传到 Git 仓库。备份实际数据时，请先停止程序，再备份整个 `instance` 文件夹。

## 修改教师密码

在项目目录执行：

```powershell
python app.py set-password
```

输入两次新密码即可，重启程序不会把密码恢复为初始密码。

也可以在**第一次启动之前**设置环境变量 `ADMIN_PASSWORD` 指定初始密码；数据库已经存在时该变量不会覆盖密码。

## 局域网演示

如果希望同一网络中的手机或其他电脑访问，在教师电脑上执行：

```powershell
# Windows PowerShell
$env:HOST = "0.0.0.0"
python app.py
```

```bash
# Ubuntu / Debian
HOST=0.0.0.0 python3 app.py
```

学生访问 `http://教师电脑的局域网IP:5000`。同一电脑测试使用 `127.0.0.1` 即可；其他设备不能使用这个地址。请确认双方能互通，且系统防火墙允许 Python 的入站连接。校园网可能禁止设备之间互访，演示时可改用同一个手机热点。

“打开签到页”使用当前浏览器访问服务的地址；在局域网演示时，教师也应使用电脑的局域网 IP 访问。

端口 5000 被占用时，可设置 `PORT` 改为其他端口，例如 PowerShell 执行 `$env:PORT = "5001"` 后启动。

## 测试

安装依赖后，在项目目录执行：

```powershell
python -m unittest discover -s tests -v
```

测试使用独立的临时数据库，覆盖完整签到与导出、重复提交、并发重复提交、到期与手动结束、登录与 CSRF 校验、非法输入、页面转义及数据持久化，不会修改实际数据。

交付前已在 Python 3.12 + Flask 3.1.2 环境通过 8 项集成测试，并验证实际 HTTP 请求中的登录、创建签到、签到回执、查看记录与 CSV 导出。JavaScript 语法检查通过；当前环境未完成浏览器视觉检查。

## 实验中的 Git 提交

在 Gitee 新建一个空仓库后，在项目目录执行，远程地址换成你自己的：

```bash
git init
git add .
git commit -m "feat: 实现简易课堂签到系统"
git branch -M main
git remote add origin https://gitee.com/你的用户名/attendance-system.git
git push -u origin main
```

可用于后续功能扩展的一个小任务：**增加签到记录按学号筛选**。当前版本保留基础流程，方便阅读和修改。

## 适用范围

本项目按课程实验设计：学生身份由填写的学号和姓名表示，未接入学校账号认证，也没有定位或人脸核验，因此不能判断是否代签。默认用 Flask 开发服务器在本机运行；真正对外部署时，需要修改初始密码、使用生产服务器和 HTTPS。

开发参考：[Flask 官方文档](https://flask.palletsprojects.com/en/stable/)、[Flask SQLite 教程](https://flask.palletsprojects.com/en/stable/tutorial/database/)。

## 许可证

MIT，允许用于学习、修改和再分发，详见 `LICENSE`。
