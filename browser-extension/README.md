# Language Coach Browser Bridge

## 安装

1. 保持 Language Coach 本地服务运行。
2. 在 Edge 打开 `edge://extensions`，或在 Chrome 打开 `chrome://extensions`。
3. 在本目录执行 `pnpm install` 和 `pnpm build:edge`。
4. 开启开发人员模式，选择“加载解压缩的扩展”，指向 `.output/edge-mv3`。
5. 在 Language Coach 的“生词本”页面复制本地连接令牌。
6. 打开扩展设置，填写服务地址和令牌，点击“保存并测试”。

## 网页全文

在网页空白处打开右键菜单，选择“导入当前页面到 Language Coach”。插件使用 Defuddle 提取主要正文，并以完整原文保存到文章池。

## 翻译

启动服务前设置 `DEEPL_API_KEY` 即可启用选段翻译。未配置时，查词与保存仍然可用。

## 技术基础

插件使用 WXT + TypeScript，并使用 Defuddle 提取正文。两者均为 MIT License。陪读蛙（Read Frog）用于架构评估，没有复制其 GPL-3.0 业务源码；详见 `THIRD_PARTY_NOTICES.md`。
