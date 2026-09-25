# 17-floortile（铺地砖）

Floortile — 面积/单片面积向上取整再加损耗百分比

## 启动

```bash
docker compose up --build
```

| 入口 | 地址 |
| --- | --- |
| 前端 | http://localhost:4600 |
| API | http://localhost:9600 |

## 主链

房间尺寸+砖规格+损耗 → 片数 → 铺贴预览

## 技术栈

Python 3.12 + FastAPI + SQLite；Vue 3 + Vite + Nginx。
