---
name: deadlock-character-mod
description: 制作和修复 Deadlock 角色 VPK mod：纹身转 UV、颜色/法线/粗糙度、半透明衣边、新版 attachment 与相机挂点对应；也可按路径或扩展名删除 VPK 内文件（如 vnmskel_c），支持单包、批量、备份与重新打包校验。不用于一般 Blender 动画重定向。
---

# Deadlock 角色 mod 制作与修复

沿用用户的模型、图案与材质选择。先确认输入包、目标材质和当前有效版本，再编辑最小范围的资源。区分“不透明度 0.3”（保留约 30%）和“透明度 0.3”。

## 选择工作流

- 纹身、指甲、毛发、UV 转移：读 [references/texture-baking.md](references/texture-baking.md)。
- 衣服半透明、金属区域透明、衣边轮廓：读 [references/clothes-opacity.md](references/clothes-opacity.md)。
- 更新后相机偏位、不跟随或特效挂点异常：读 [references/attachments.md](references/attachments.md)，先审计再修补。
- 编译、VPK 替换、变体与校验：读 [references/compile-package.md](references/compile-package.md)。
- 删除包内文件、去除骨骼覆盖、批量清理：读 [references/vpk-removal.md](references/vpk-removal.md)，先查看实际命中条目。
- 本机工具位置、Celeste 的对象/材质及现有产物：需要继续该项目时读 [references/local-project.md](references/local-project.md)。这些名字、坐标和包号都是项目实例，不能当成所有角色的常量。

## 工作约定

1. 列出源包内部条目，定位模型、材质和实际引用的纹理；不要靠文件名猜测当前生效资源。检查 addons 中同一路径的覆盖包。比较模型/条目散列再归因。
2. 保留干净原图、原法线、原粗糙度和输入包，记录源文件 SHA256。按用户指定顺序生成纹身/无纹身及透明/不透明变体。
3. 需要 AI 绘制或补全图案时先用内置 `image_gen`，并遵守当前 imagegen skill 和用户的本机回退授权。用确定性的几何投影、遮罩和编译处理 UV/法线/通道数据，不让生成模型重画整张 UV 或移动岛。
4. 身体、衣服、头发等实际材质分别处理。不要把 `clothes2`、装饰材质或身体一起改，除非用户要求。
5. 只改计划内的归档条目；编译产生的新纹理引用必须完整入包。独立校验编译数据、所有条目的 CRC32、归档 MD5 和包内资源依赖。
6. “文件可解析 / 哈希通过 / 数值正确”不等于“游戏中已验证”。明确记录是否已进游戏检查，以及当前仍不确定的效果。

## 输出与操作范围

- 默认输出工作区中的新包，不覆盖输入。用户要求数字加一时，从指定基包与现有包号选无冲突编号；不要覆盖已有文件。
- “只制作、不安装”持续适用，直到用户改变要求。制作授权不自动变成复制进游戏 addons 的授权。
- 用户要求清理无效旧包时，在新包校验完成后按精确文件名删除已确认无效版本。保留仍有用途的基包，不泛删 addons 或工作区。
- 交付完整绝对路径、每个包的变体说明、实际验证结果与未做的游戏测试。不要把推断或未验证修复写成已解决的事实。

## 可用脚本

脚本均在本 skill 的 `scripts/` 中；先运行 `--help`。普通 Python 脚本只依赖标准库，衣边烘焙在 Blender 内运行。

- `vpk_patch.py`：统一清单、CRC/MD5 验证、替换/添加或按明确选择器删除条目，输出新 VPK，不覆盖输入。
- `remove_vpk_entry.py`：删除工作流的兼容入口，默认精确匹配 `vnmskel_c` 扩展名，支持文件夹批量与 dry-run。默认输出新包；只有显式 `--in-place` 才会先备份再原子替换。
- `attachment_audit.py`：调用指定的 Source2Viewer CLI，对比两个已解包模型的 attachment、骨骼父节点和相机键；可在明确选用兼容回退时生成修正模型并验证回读。
- `bake_clothes_border.py`：按实际模型边界和可选尖锐收边生成透明度遮罩，先合并同位置顶点，避免把 UV 拆分缝画成轮廓。

脚本不处理未知格式或骨骼坐标系不匹配的通用转换。遇到这类情况保留报告，改用对应格式的新解析器或原生编译路径，不能悄悄跳过错误。
