# 编译与 VPK

## 编译隔离

建工作区内 `content/<game>/` 与 `game/<game>/`，复制必要的 `gameinfo.gi`、当前工具需要的模块及源贴图。让 gameinfo 搜索到本机对应游戏/SDK 的 core 与 shader 内容。不要为解决一次编译改写用户全局配置或覆盖原材质。

本机已用过：

```powershell
& $resourcecompiler -i $materialSource -f -nop4 -game $isolatedGame -contentroot $isolatedContent
```

Celeste 的 Reduced_CSDK_12 曾出现 particles schema 模块不匹配；本项目对纯纹理/材质编译使用过 `-danger_mode_ignore_schema_mismatches` 并取得成功汇总。这是该 SDK 的特例，不应默认加到其他任务，也不证明可安全重编译复杂模型/动画。先查正确工具版本。

有些本机 resourcecompiler 在输出成功汇总后进程仍不退出。以明确的成功汇总、产物时间及解析结果判断，不无限轮询或杀掉所有同名进程。

## 编译结果验证

- 解码 `.vmat_c` 的 DATA/RED2，检查 shader、features、opacity scale、角度参数及纹理引用。
- 解码实际引用的新 `.vtex_c`，检查颜色/透明度/金属度/粗糙度通道。BC 压缩可有数值偏差；按误差统计验证，不要求 alpha 每像素与 PNG 完全相等。
- 入包依赖按编译材质的引用解析，不按猜测的文件名；引用的默认材质资源应确认包内或当前游戏搜索路径可解析。
- 不改变不相关材质/图像字节；变体间差异应与用户需求完全对应。

## VPK 替换

脚本对原包做读取与 CRC 验证，使用新名字输出。替换映射 JSON 中的键为真实内部路径，值为本地编译文件路径；相对路径以映射 JSON 所在目录解析。例如：

```json
{
  "models/heroes_wip/unicorn/unicorn.vmdl_c": "unicorn_fixed.vmdl_c"
}
```

```powershell
& $python "$skill/scripts/vpk_patch.py" list $sourcePak
& $python "$skill/scripts/vpk_patch.py" verify $sourcePak
& $python "$skill/scripts/vpk_patch.py" patch $sourcePak --replacements $mapping --out $newPak
& $source2cli -i $newPak --vpk_verify
```

默认映射只能替换已有条目；确需加入新编译纹理时加 `--allow-add`。脚本拒绝覆盖现有输出、拒绝原地修改、拒绝把官方签名包当成可重签包。分卷源包必须与 `_NNN.vpk` 文件同时可读。

删除已有条目使用同一工具的 `remove` 子命令。单包、批量及备份约定见 [vpk-removal.md](vpk-removal.md)，不要另用旧实现保留压缩前的分块 MD5 表。

VPK v2 结构为头、目录树、数据区、archive-MD5、other-MD5、签名区，不能用 ZIP 重压。重新计算所有 CRC32、每 1 MiB 数据块 MD5，以及：

1. MD5(tree)
2. MD5(archive-MD5 section)
3. MD5(从文件开头直到上述两个 MD5 之后的所有字节)

比较每个条目的前后散列，确保只改变替换映射里的内容；保存源/输出 SHA256 和验证报告。官方包只作为只读基线，新增 mod 不声称拥有有效官方签名。

## 安装和清理

用户已要求“只制作不安装”时，仅给出新包与状态。若后来授权安装，处理同一内部资源路径的旧覆盖包，避免多版叠装；不要随意禁用其他角色 mod。删除旧包只针对用户授权且确认无效的精确路径，新包验证完成后执行。
