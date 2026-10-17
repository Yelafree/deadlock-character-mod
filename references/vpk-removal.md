# 删除 VPK 内文件（融合 vpk-entry-remover）

目标是删除归档目录中的指定条目并重建有效 VPK；不是删除整个磁盘包，也不是把内部 payload 当 ZIP 项直接删字节。删除选择器按用户需求解析，不能一看到角色 mod 就自动删骨骼。

## 单包：统一入口

```powershell
& $python "$skill/scripts/vpk_patch.py" remove $pak --ext vnmskel_c --dry-run
& $python "$skill/scripts/vpk_patch.py" remove $pak --ext vnmskel_c --out $cleanPak
```

`--ext` 精确匹配扩展名；`--match` 匹配路径中的子串；`--entry` 匹配完整内部路径。可重复，条件按 OR 合并。例如只删某个指定材质要用 `--entry`，不要用宽泛 `--match clothes` 连贴图一起删。

先显示命中的完整路径、所属源包，确认与用户授权范围相符。用户已明确要求删除的条目，不再机械地追问确认；若描述不足以确定目标且 dry-run 匹配到多个不相关条目，再提出具体问题。

路径因角色和 mod 而异，不能写死成某个英雄目录。无匹配时说明包内没有该条目或选择器有误，不重复运行同一命令。拒绝删除全部条目，也不重写游戏官方签名包。

## 文件夹批量与旧用法入口

```powershell
# 无选择器时，兼容入口默认针对精确 vnmskel_c 扩展名。
& $python "$skill/scripts/remove_vpk_entry.py" $folder --dry-run
& $python "$skill/scripts/remove_vpk_entry.py" $folder --report "$work/removal-report.json"

# 明确要求原地处理时，每个源包先备份，再原子替换。
& $python "$skill/scripts/remove_vpk_entry.py" $folder --in-place --report "$work/removal-in-place.json"
```

默认只枚举一层文件夹，加 `--recursive` 才进入子目录。批量任务先 dry-run，按返回清单核对范围；不把工作区父目录或整个 SteamLibrary 当成方便的默认输入。

默认新包名为 `<原stem>_clean.vpk`；可用 `--out` 指定单包输出。已有输出不会覆盖。显式原地操作时，先生成并校验完整新包，再创建 `.bak`、`.bak2` 等不覆盖已有备份的硬链接（失败时复制），最后原子替换；验证失败恢复备份。不提供跳过备份或跳过验证的快捷参数。

目录扫描跳过 `_000.vpk` 这类数据分卷，真正入口是 `_dir.vpk`。其他损坏/未知归档不能默默当作成功处理。分卷源包的伴随数据文件需保持可读；输出重建为单个自包含 v2 包。

兼容入口退出码：0 有匹配并完成（或 dry-run 有命中）；3 全部无匹配；1 至少一个归档处理失败；2 参数问题。逐包报告成功、未命中和失败，不因一个包失败丢掉其他结果。

## 校验和骨骼特殊情况

删除后验证：目标不在目录、其余 payload 字节完全一致、每条 CRC32、archive 分块 MD5 和三个 OtherMD5 都正确。重建数据偏移后必须重新计算分块 MD5，不能把旧分块校验表原样保留。再用 Source2Viewer `--vpk_verify` 独立复核。

删除 mod 的 `.vnmskel_c` 不等于删除 `.vmdl_c` 对骨骼路径的引用；意图通常是让游戏回退到其当前骨骼资源。先核对当前游戏确有同一路径回退，并检查自定义网格与该骨骼的绑定兼容性。用户已明确要求去掉骨骼覆盖时可按授权执行并说明未验证的游戏风险，不额外要求同意。

相机偏位可能来自 attachment，动画变形可能来自骨骼绑定；不要用删骨骼作为所有新版问题的通用修复。需要对应挂点时读 [attachments.md](attachments.md)。
