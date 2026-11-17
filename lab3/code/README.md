# 校园拾光

Python 3.11 及以上。运行时使用标准库和本机 SQLite。

## 安卓版

1. 在电脑的 `code` 目录双击 `启动校园拾光.cmd`。它会创建演示库并打开同一套浏览器界面。
2. 在 Android Studio 启动模拟器，或用 USB 连接已开启调试的安卓手机。
3. 从 `code` 运行安装脚本。脚本会安装 APK、建立本地转发并打开「校园拾光」。

```powershell
powershell -File android/install.ps1
```

也可用 Android SDK 的 ADB 手动安装和转发：

```powershell
adb install -r campus-market-debug.apk
adb reverse tcp:8871 tcp:8871
```

安装需要 Android 8.0 或更高版本。手机端连接电脑上运行的后端，演示时需要保持后端和转发运行。
重连设备后，重新执行转发命令。设备不止一个时，用 `adb -s 设备编号` 指定。
演示账号为 `buyer`、`seller`、`moderator`，密码都是 `campus-demo-2026`。
三种角色分别登录后，即可通过按钮完成发布、审核、预约、交付和确认。
这些演示数据单独保存于 `data/visual-demo.db`。

建立自己的空库时，运行 `python -m campus.mobile --open`，在「我的」初始化管理员再注册普通账号。

### 构建 APK

准备 JDK、Android SDK 平台 35 与 Build-Tools 35.0.0，再从 `code` 运行：

```powershell
powershell -File android/build.ps1 -SdkRoot "你的 SDK 路径" -JdkRoot "你的 JDK 路径"
```

安装包位于 `build/apk/campus-market-debug.apk`。脚本使用 AAPT2、javac、D8、zipalign 与 apksigner 构建并校验签名。
客户端通过 WebView 显示本机后端提供的界面，使用同一套 Python 服务和 SQLite 数据库。

## 命令行版

```powershell
python -m campus --db data/market.sqlite3 --setup-admin moderator
python -m campus --db data/market.sqlite3
```

在程序中输入 `help` 查看全部命令，输入 `命令 --help` 查看参数。
商品、预约和用户编号由数据库生成。以下示例使用空库，实际以程序输出为准。

```text
register seller
register buyer
login seller
create "算法教材" "无缺页" 35.50 --category books --request book-1
submit 1
login moderator
review 1 approve "符合发布要求"
logout
search --category books --min 30 --max 40
item 1
login buyer
reserve 1 35.50 3 --request reserve-1
login seller
records sell
accept 1
deliver 1
login buyer
complete 1
records buy
quit
```

密码按终端提示输入。当前账号可以通过 `login` 切换。
`create` 可以使用多个 `--image 路径` 参数，`save-image` 可以导出原图。
预约时请使用 `item` 返回的价格和版本。重试创建操作时复用原请求编号。
程序运行时会周期性关闭过期预约，重启后也会处理已经过期的预约。
`--deadline 5` 可用于本地演示超时。

```powershell
python -m pip install build pylint
python -m compileall -q campus
python -m unittest discover -s tests -v
python -m tools.verify_load
python tools/loc.py
python -m pylint campus
python -m build --wheel --outdir build/dist
```

`tools/loc.py` 只统计 campus 下的 Python 源码，排除空行、注释和文档字符串。
SQLite 使用整数分保存价格，用部分唯一索引保护有效预约，并在事务中同时更新商品、预约及审计记录。统计日期用 UTC 解释。
尚未确认的校内认证、争议强制结案、冻结恢复和报表导出均未开放。
