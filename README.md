# 课堂签到系统

基于 Flask 和 SQLite 的课堂签到系统。教师发起签到，学生输入签到码、学号和姓名完成签到，教师可以查看记录并导出 CSV。

## 功能

- 教师登录，创建和管理签到。
- 自动生成 6 位数字签到码，可设置有效时长，也可提前结束。
- 同一次签到中，同一学号只能提交一次。
- 查看历史签到、签到人数和记录明细。
- 导出 CSV 文件，支持 Excel 打开。

## 运行

运行环境：Python 3.12。

在项目目录执行：

```bash
python -m pip install -r requirements.txt
python app.py
```

首次启动会自动创建数据库。启动后访问：

| 页面 | 地址 |
| --- | --- |
| 学生签到 | http://127.0.0.1:5000/ |
| 教师登录 | http://127.0.0.1:5000/teacher/login |
| 教师工作台 | http://127.0.0.1:5000/teacher |

初始教师账号为 `admin`，密码为 `admin123`。

## 使用

1. 教师登录工作台，填写课程名称、签到主题和有效时长，点击“生成签到码”。
2. 学生打开签到页面，填写签到码、学号和姓名，提交后查看签到回执。
3. 教师在签到详情页点击“刷新”查看记录，点击“导出 CSV”下载文件。

签到到期后自动停止接收，也可以点击“提前结束签到”手动关闭。页面和导出文件中的时间均为北京时间。

## 修改密码

在项目目录执行：

```bash
python app.py set-password
```

按提示输入两次新密码，密码长度至少为 8 位。

首次启动前也可以通过环境变量 `ADMIN_PASSWORD` 设置初始密码。数据库创建后，该变量不会覆盖已有密码。

## 局域网访问

允许同一网络中的其他设备访问时，将监听地址设为 `0.0.0.0`。

Windows PowerShell：

```powershell
$env:HOST = "0.0.0.0"
python app.py
```

Linux：

```bash
HOST=0.0.0.0 python3 app.py
```

其他设备访问 `http://服务器的局域网IP:5000`，并确保防火墙允许访问该端口。

默认端口为 `5000`，可通过环境变量 `PORT` 修改。例如在 PowerShell 中执行：

```powershell
$env:PORT = "5001"
python app.py
```

## 项目文件

| 文件或目录 | 说明 |
| --- | --- |
| `app.py` | 登录、签到管理、记录查询和 CSV 导出 |
| `schema.sql` | 数据库表结构 |
| `templates/` | 页面模板 |
| `static/` | 样式、脚本和图标 |
| `requirements.txt` | Python 依赖 |
| `tests/test_app.py` | 业务流程测试 |

运行数据保存在 `instance/` 目录：

- `attendance.db`：教师账号、签到活动和签到记录。
- `secret.key`：用于签名登录会话的密钥。

该目录已在 `.gitignore` 中排除。备份时先停止程序，再复制整个 `instance/` 目录。

## 测试

在项目目录执行：

```bash
python -m unittest discover -s tests -v
```

测试覆盖登录、签到、重复提交、有效期、手动结束、CSV 导出和数据持久化等流程，使用独立的临时数据库。

## 许可证

[MIT](LICENSE)