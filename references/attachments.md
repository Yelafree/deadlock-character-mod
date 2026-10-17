# 游戏更新后的 attachment 与相机

## 基线和诊断

从本机当前游戏的 `pak01_dir.vpk` 解出原模型及需要的骨骼资源，以当前版为基线；旧 SDK、旧 blend、旧 mod 不能代替当前原模型。用户说“原模型”可能指游戏模型也可能指 blend 内原对象，按故障背景判断并说明基线。

1. 比较各变体的 `.vmdl_c` SHA256。如果相同而材质不同，不能把相机差异直接归因于透明材质。
2. 对比所有 MDAT 中的 `m_attachments`：挂点名、父骨骼名、影响权重、旋转四元数、偏移、ignore-rotation 和 root-transform 标志。
3. 同时对比 DATA 中 `m_modelSkeleton`、`m_keyValueText` 的 `CitadelCameraSettings_t` 与 `AttachmentCameraData`、动画图及骨骼引用。
4. 先核对同名骨骼的父层级与局部/世界绑定变换。父骨骼坐标系不一致时，不可直接复制原模型局部挂点；应计算坐标转换或修复导入流程。
5. 有些模型把同一挂点表复制进多个 MDAT；修正时覆盖所有相关子网格，不只处理第一张表。

## Celeste 案例，不能作为通用坐标常量

2026-10-17 本机当前原模型与这批 mod 的根骨骼 `root_motion` 朝向一致，但 `near_00` 偏移由原模型约 `[-14, -30, 85]` 变成 mod 的 `[-30, 85, -14]`，其他 `near_*`、`far_*`、`gunaim_*`、`portrait_camera` 等也有轴顺序/旋转差异。

原/改模均有 46 个挂点；26 个精确数值不同，其中部分只是浮点精度差。按数值容差与实际差异大小区分，别把 1e-6 误差都报告为故障。原模型还有 mod 缺失的 `AttachmentCameraData`；原有 `CitadelCameraSettings_t` 则已经一致。

本次补丁对 6 个 MDAT 恢复当前原模型挂点表，给 DATA 的游戏键添加缺失的相机表。网格几何缓冲、动画、物理、外部资源引用字节保持一致；其他解码字段保持一致。四包校验通过，但游戏内相机跟随尚待用户验证。**不要将此案例写成已确认解决全部新版相机问题的结论。**

## 工具与修补

```powershell
& $python "$skill/scripts/attachment_audit.py" --cli $source2cli `
  --original $currentGameModel --mod $customModel --out-dir "$work/attachment-audit"
```

优先使用支持当前资源版本的 CLI。旧 CLI 20.0 读取本次新游戏模型时出现 `Unknown KVType ... 26 (0x1A)`；更新到支持该资源的解析器后再处理。不要把未知块改名、丢弃 RED2/MDAT 来绕过解析，或把失败的空输出当成功。

首选保留 KV3 类型/精度的原生编辑或编译路径。脚本提供的修补属于**兼容回退**：从 CLI 文本解码重写相关 MDAT/DATA 为旧版未压缩 binary KV3，其余资源块字节保留。文本浮点精度、数值类型和 KV3 版本可能改变；必须回读比较所有非目标字段，并明确未做游戏测试。使用时显式选择：

```powershell
& $python "$skill/scripts/attachment_audit.py" --cli $source2cli `
  --original $currentGameModel --mod $customModel --out-dir "$work/attachment-audit" `
  --patch-model "$work/unicorn_fixed.vmdl_c" --allow-legacy-kv3
```

脚本遇到缺失父骨骼或绑定变换不一致即停止。不能因赶工跳过这个检查。脚本不会改包、安装或删除旧包；模型验证后再通过 VPK 替换工具生成各版本。

不要默认删除或加入 `.vnmskel_c`。先查包内是否真的覆盖骨骼、动画图是否引用它，以及当前版本的绑定关系；额外骨骼和排序不同本身不等于应删除。
