# 衣服透明与固定衣边

## 先对照实际透明材质

从用户指定包中解出 `clothes` 与已有效的 `clothes2`，比较编译后的 DATA、RED2 中的渲染属性、纹理引用与通道。源 `.vmat` 不一定对应包内当前版本。

Celeste 的已知模板：`pbr.vfx`，`F_TRANSLUCENT 1`，`F_DISABLE_Z_PREPASS 1`；旧不透明衣服开启了 `F_GLASS 1`。可基于当前 `clothes2` 的设置构建新的 `clothes`，替换为 `clothes` 自己的颜色、法线、金属、AO 和粗糙度来源，而不是把 `clothes2` 的整套贴图套到衣服上。

核对编译后 `translucent = 1`、`WriteDepthBeforeAlphaBlending = 0` 等属性。切换透明组合后，应有实际透明通道，并保持金属度来自独立正确资源；不能把原来装在颜色 alpha 中的金属度直接当透明度。

`g_flOpacityScale1` 可以做整体不透明度控制；常量白透明遮罩配 0.3 的 scale 曾用于排除金属遮罩干扰。不要仅凭一个开关或贴图数值宣称游戏效果已生效。

## 固定衣边和视角轮廓是两类需求

用户说“下摆/开口/衣服边缘存在轮廓”时，优先理解为固定在衣物结构上的边。不能只调 `g_flAlphaAnglePower1` 或 Fresnel 作为替代。若用户明确要视角轮廓，再独立处理角度响应，并先验证正负号及最终组合公式。

固定边的实现：

1. 用实际 mesh 的相同位置顶点合并后的拓扑识别开放边；按需加入材质交界和尖锐收边。**UV 岛边界不等于衣服边界**。
2. 沿选定材质的网格邻接计算距离场，窄边高不透明度、内部低不透明度，平滑过渡。
3. 光栅化回该材质 UV，并在未覆盖 texel 中扩边。别穿过其他 UV 岛。
4. 关闭额外角度调制，把整体 scale 设为 1，让贴图直接控制固定衣边。

运行：

```powershell
& $blender -b $blend --python "$skill/scripts/bake_clothes_border.py" -- `
  --object CLothes --material Clothes --out "$work/clothes_border.png" `
  --size 2048 --interior 0.18 --border 0.60 --solid-width 0.045 --fade-width 0.24 --crease-angle 80
```

宽度是网格本地长度单位，不是通用厘米。换角色或缩放对象后要调。`--crease-angle 180` 可基本关闭尖锐折边，只保留开放边/材质边界。细长配件可能几乎全被高不透明度窄边覆盖，需要模型预览判断。

Celeste 本次遮罩由 178 条开放边与 454 条尖锐边生成；2048 编译颜色通道解码后，内部 alpha 均值约 0.1804、固定边约 0.5997。它们是**文件级验证结果，尚未证明游戏中轮廓与相机行为符合预期**。

透明不生效时依次检查：当前装的是哪个包、同一路径覆盖、编译后渲染属性、颜色 alpha 与独立金属通道、opacity scale、角度响应、多层衣物叠加与深度设置。先取得证据再归因，避免反复改同一开关。
