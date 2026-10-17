# 本机 Celeste 项目实例

以下路径是发现线索，先检查是否仍存在、工具是否兼容，再使用。不得把这些路径写死进其他用户或其他角色的流程。

| 资源 | 本次位置 |
|---|---|
| 工作目录 | `D:/DeadLockModding/BlenderMesh/celeste` |
| 原场景 | `celeste1.blend` |
| 普通 Python | `C:/CodexPy/python.exe` |
| Blender | `D:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe` |
| 最新已用 CLI 20.1 | `camera_fix_work/vrf20_1/Source2Viewer-CLI.exe`，本地随修复任务下载；需存在性/版本检查 |
| 旧 CLI 20.0 | `D:/DeadLockModding/Tools/Source2Viewer-CLI.exe`；能解析旧 mod，但本次不能解析新游戏模型 |
| SDK | `D:/DeadLockModding/Reduced_CSDK_12/Reduced_CSDK_12` |
| SDK 编译器 | `<SDK>/game/bin/win64/resourcecompiler.exe` |
| 游戏 addons | `E:/SteamLibrary/steamapps/common/Deadlock/game/citadel/addons` |
| 当前原模型包 | `E:/SteamLibrary/steamapps/common/Deadlock/game/citadel/pak01_dir.vpk` |

本机普通 Python 无 numpy，Blender 自带 numpy；普通 Python 的 PIL 可用。不要为图像任务临时安装依赖或尝试受限的系统 Python。实际会话的 AGENTS.md 对图像生成回退与环境变量有额外要求，使用时读当前授权，不复制密钥进脚本或 skill。

## 对象与资源

- 自定义衣服对象 `CLothes`，材质依次为 `Clothes2`、`Clothes`、`Decorate`。
- 自定义身体对象 `models/heroes_wip/unicorn/unicorn.vmdl_c.unicorn_body.003`，材质 `Body`。
- 原身体 `models/heroes_wip/unicorn/unicorn.vmdl_c.unicorn_body`，blend 内可能隐藏。
- 材质来源 `<SDK>/content/citadel_addons/celeste/models/heroes_wip/unicorn/materials`。
- 模型条目 `models/heroes_wip/unicorn/unicorn.vmdl_c`。
- 身体颜色 `.../materials/body_basecolor.1001_png_84ebbec8.vtex_c`。
- 身体法线/粗糙度打包资源 `.../materials/body_normal.1001_png_9a894dfd.vtex_c`。
- 衣服材质 `.../materials/clothes_m.vmat_c`；半透明参照 `clothes2_m.vmat_c`。

## 项目脚本作为实例

工作目录中保留了 `transfer_tattoos.py`、`transfer_leg_tattoos.py`、`paint_toenail_edges.py`、`make_no_tattoos_nails.py`、`bake_feathered_heart_hair.py`、`soften_heart_hair_edges.py` 与多种预览脚本。这些包含角色专用 ROI、世界坐标和文件名，适合检查算法与继续同一项目；运行前必须核对输入，不能当成通用工具直接运行到另一角色上。

## 2026-10-17 包谱系

| 包 | 内容 | 验证状态 |
|---|---|---|
| 46 / 47 | 有 / 无纹身，蓝粉毛发与指甲，原衣服设置 | 基础纹理包，旧 attachment |
| 48–51 | 早期透明尝试 | 用户反馈无效，已按授权删除 |
| 52 / 53 | 有 / 无纹身，clothes 整体 0.3 不透明度 | 文件校验通过，旧 attachment |
| 54 / 55 | 有 / 无纹身，内部约 0.18、固定衣边约 0.60 | 编译通道与 VPK 校验通过，旧 attachment |
| 56 / 57 | 46 / 47 加当前原模型 attachment 对应 | 文件校验通过，未安装；游戏效果待验证 |
| 58 / 59 | 54 / 55 加相同 attachment 修正 | 文件校验通过，未安装；游戏效果待验证 |

包号是历史记录，不是未来要使用的默认输出编号。当前有效版本取决于用户之后的游戏反馈和 addons 状态；不要仅因这里记录了 56–59 就宣称已经安装或有效。
