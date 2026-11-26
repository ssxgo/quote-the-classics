# 古籍翻阅

Vue 3 古籍阅读器，收录仓库所附版本的《论语》20 篇 512 章句和《道德经》81 章。每条正文附白话释义、文意示意，以及带出处的典故或语境。支持白话检索、原文相似度、繁体翻页和简体对照。

## 本地运行

Windows 下双击仓库根目录的 [启动网页.bat](../启动网页.bat)。脚本会准备依赖、构建网页，并在服务就绪后打开浏览器。关闭启动窗口或按 Ctrl+C 可停止本次启动的服务。

也可以从仓库根目录在 PowerShell 手动启动。需要 Node.js 20.19+ 或 22.12+、pnpm 11、uv 和 Python 3.12。

```powershell
Set-Location web
uv sync --locked --python 'C:/Users/13894/Documents/Codex/python-ml/.venv/Scripts/python.exe'
pnpm install --frozen-lockfile
pnpm build
uv run --locked uvicorn server:app --host 127.0.0.1 --port 8000
```

打开 [本地阅读器](http://127.0.0.1:8000)。若电脑没有上述路径，可用 `uv sync --locked --python 3.12`。uv 会在 `web/.venv` 安装依赖；安装结束后，阅读和检索均在本机完成。

开发时在第一个 PowerShell 执行 `$env:CLASSICS_WEB_DEV='1'`，再运行 `uv run --locked uvicorn server:app --host 127.0.0.1 --port 8000`。在另一个终端运行 `pnpm dev` 并打开 Vite 打印的地址。Vite 会将 API 请求代理给本机 Python 服务。

## 数据与验证

`pnpm corpus` 将仓库正文和两书的注解合并为网页数据。繁简转换用于字形展示，章段编号沿用数字底本。`pnpm index` 沿用仓库的 BGE 模型，分别对原文和白话资料（本页释义、原有检索提示）生成索引。缓存保存在 `.index/`，数据或模型变动后会重新生成。搜索优先纳入原文匹配，再按相关性补足最多 8 条候选。列表按输入与原文最相近分片的余弦相似度降序排列。语义检索不可用时，网页仍可按原文字词匹配。

两书正文、检索资料和模型放在 [data](data)。正文底本信息见 [catalog.json](data/catalog.json)，语义模型采用固定修订的 Xenova 量化版，繁简字形使用 OpenCC.js。第三方许可证见 [data/licenses](data/licenses)。[BGE 原版](https://huggingface.co/BAAI/bge-small-zh-v1.5) · [Xenova 量化版](https://huggingface.co/Xenova/bge-small-zh-v1.5/tree/75c43b069aac4d136ba6bc1122f995fedcfd2781) · [OpenCC.js](https://github.com/nk2028/opencc-js)

「版本与来源」列有正文版本和许可证。页面使用大都会艺术博物馆公版藏品 [《夏山图》](https://www.metmuseum.org/art/collection/search/39915)，版式参考 [「皕宋——故宫宋版图书观止」](https://theme.npm.edu.tw/exh114/TwoHundredTreasures/)。

《论语》释义沿用并整理项目的现代汉语检索释义。古注按原文对齐朱熹 [《四书章句集注》](https://zh.wikisource.org/wiki/四書章句集註/論語集注卷一) 和何晏、邢昺 [《论语注疏》](https://zh.wikisource.org/zh-hans/論語註疏/卷13)。古注摘录保留出处，按网页字形整理。《道德经》参照 [王弼本《道德经》](https://zh.wikisource.org/zh-hans/道德經_(王弼本)) 撰写逐章释义。有相关典故时附该典故的原始文献链接。对照版本出现异文时，网页正文保留仓库底本。

```powershell
pnpm test
pnpm build
uv run --locked python -m unittest
```
