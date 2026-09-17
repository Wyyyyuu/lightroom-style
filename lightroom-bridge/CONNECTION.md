# Lightroom 本地 SDK 桥接

0.2.3.0 已在本机 Lightroom Classic 13.0.2 验证：指定图像导入、虚拟副本、影调/白平衡/HSL/颜色分级、参数曲线及 RGB 综合点曲线写入、颗粒数量/大小/粗糙度、独立回读以及 Lightroom 原生 JPEG 导出。仅在 PhotoStyle- 虚拟副本上写入，原片受保护。不是图像生成或外部脚本调色。

完整操作与恢复说明集中在 [技能桥接流程](../lightroom-style/references/bridge.md)。工作区 bridge_probe.py 对应发布版 scripts/lightroom_probe.py，bridge_client.py 对应 scripts/lightroom_client.py。PhotoStyleBridge.lrplugin 是插件源码；发布时将 Lua 文件复制到技能 assets/PhotoStyleBridge.lrplugin，不打包日志、旧版备份或测试依赖。

Windows 插件安装位置通常为 %APPDATA%\Adobe\Lightroom\Modules\PhotoStyleBridge.lrplugin；状态目录为 %APPDATA%\Adobe\Lightroom\PhotoStyleMatchBridge。管理器按钮“运行只读连接检查”只产生诊断；新版后台收到具体请求后才执行对应操作。菜单同时注册文件与图库入口。

```text
python bridge_probe.py --timeout 15
python bridge_client.py read --catalog "CATALOG.lrcat" --path "TARGET.jpg" --photo-id PHOTO_ID
```

每次操作验证新回执，不自动重复修改请求；超时用 status --request-id 查询原 ID。命令模块动态加载，常规修复无需反复重启 Lightroom。Bootstrap 改动需要在管理器点击检查或重新载入；元信息版本文字仅在重载后刷新。

## 验证

工作区 tests/test_lightroom_bridge.py 和 tests/test_lightroom_commands.py 使用 Lua 5.1 + 模拟 SDK 验证边界与错误处理，不能替代实机测试。

validate_native.py 是明确的实机验收程序，会导入它新建的程序化色阶图、创建副本、实际调色和导出。Pillow 只创建输入图表及只读测量 Lightroom 导出，不渲染调色结果。只能在需要实机验收且已获授权时运行，不能为普通调色请求自行重复造测试图。

```text
python validate_native.py --catalog "CATALOG.lrcat" --run-dir "NEW_VALIDATION_DIRECTORY" --state-dir "BRIDGE_STATE_DIRECTORY"
```

已完成步骤与回执保存在运行目录 validation.json。恢复时不自动重发失败的修改步骤；先查 ID、读真实状态、保存失败原因，再修复。运行目录中的验收记录仅供本地诊断，不随发布包分发。
