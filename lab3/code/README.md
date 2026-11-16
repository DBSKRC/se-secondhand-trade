# 校园拾光

Python 3.11 及以上。运行时使用标准库和本机 SQLite。

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
