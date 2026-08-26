"""早期 FastAPI 练习使用的临时内存列表。

正式应用已经改用 SQLAlchemy 和 MySQL，本文件仅作为学习记录保留。
"""


users: list[dict[str, int | str]] = []
