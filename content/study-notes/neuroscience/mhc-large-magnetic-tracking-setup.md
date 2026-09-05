---
title: "Mobile HomeCage Large 磁追踪配置与调试"
tags:
  - neuroscience
  - study-notes
  - behavioral-neuroscience
  - neurotar
  - troubleshooting
status: "technical note"
updated: 2026-09-05
---

> [!summary] 现场结论
> 当前碳纤维笼体未安装追踪磁铁，因此软件在 Play 状态下仅显示噪声或跳变坐标。临时加入两块磁铁后，追踪随笼体运动恢复连续变化，说明 ECU、传感板、USB 驱动和软件链路基本正常，故障集中在追踪目标缺失。临时磁铁仅适合联调，不能用于正式空间定位或 Zone 闭环实验。

## 1. 适用范围

本文用于 Mobile HomeCage® Large with Tracking Capability 的：

- 硬件安装与首次软件配置；
- 无磁铁笼体的故障定位与临时联调；
- Cage and Clamp 几何参数配置；
- 正式实验前的验收与配置留档。

液体奖励和气吹执行链路见 [[study-notes/neuroscience/mhc-large-closed-loop-reward-air-puff|Mobile HomeCage Large 闭环液体奖励与气吹系统]]。

## 2. 系统组成与关键约束

| 模块                         | 功能                               | 关键约束                                   |
| ---------------------------- | ---------------------------------- | ------------------------------------------ |
| Air dispenser / 气浮平台     | 提供气膜，内部集成磁传感器板       | 奖励液不得进入气孔或传感板                 |
| Carbon-fiber cage / 碳纤维笼 | 承载动物并提供磁追踪目标           | Large 追踪笼按标准配置应在底部集成两块磁铁 |
| ECU                          | 采集传感器、USB 通信和 TTL I/O     | 传感板连接线不得带电插拔                   |
| Tracking Software            | 重建位置、速度和区域，执行闭环规则 | 磁铁几何与方向正确是可信重建的前提         |
| Bridge / clamp               | 头固定并定义实验几何               | 实际方向、中心位置与软件参数必须一致       |

根据 User Manual 3.2.4，传感器通过笼底两块轴向磁化的 NdFeB 磁铁重建运动，标准磁铁约为 Ø20 mm × 2 mm。碳纤维本身不是追踪目标；缺少磁铁时，系统仍会采集环境磁场和电子噪声，因此界面可能显示随机数据而非零值。[M1]

## 3. 标准安装与首次配置

### 3.1 机械、气路和接线

1. 将气浮平台置于稳定、水平的实验台；成像或电生理实验优先使用减振台。
2. 接入气源并逐渐增加流量，使笼体自由滑动且不出现明显悬浮间隙。Large 平台的手册参考能力约为 `150 L/min, 20 kPa`。
3. 将桥架置于中心刻度 `0`；若因实验空间移动桥架，记录实际偏移量。
4. ECU 断电后连接 sensor board 的 15-pin cable，再连接 USB 并启动 ECU。

### 3.2 串口与硬件识别

1. 首次启动软件时选择 **Setup new**。
2. 在 **Hardware Ports Configuration** 中查找并选择 `Silicon Labs CP210x USB to UART Bridge`。
3. 点击 **Test**；确认 Current port 变绿后保存。
4. 返回主界面，确认 Hardware information 显示 ECU 信息，而不是 `Not connected`。

### 3.3 计时校准

正式实验前执行 **Settings → Timings calibration**。校准时应将带标准磁铁的笼体置于气浮平台上。该操作只校准硬件与软件的时序，不会学习任意手工磁铁的空间布局。

## 4. 现场故障定位

| 现象或操作                 | 结果                     | 判断                         |
| -------------------------- | ------------------------ | ---------------------------- |
| Play 后坐标随机跳动        | ECU 信息和串口测试正常   | 通信正常，优先检查磁追踪目标 |
| 检查当前碳纤维笼底         | 未发现磁铁或磁吸反应     | 与 Large 追踪笼标准配置不符  |
| 临时固定两块磁铁后移动笼体 | 坐标随移动和旋转连续变化 | 传感板、ECU 和软件主链路正常 |
| 磁铁位置、极性和间距未标定 | 绝对位置与方向无法验证   | 只能用于功能联调             |

诊断链条为：

```text
无磁铁 → 噪声或跳变坐标
加入磁铁 → 运动响应恢复
结论     → 追踪目标缺失，而非 USB/ECU 通信故障
```

## 5. 临时磁铁方案的边界

临时磁铁可用于：

- 验证 sensor board 对磁场的响应；
- 验证 ECU、USB 和 Tracking Software 的数据链路；
- 检查平移和旋转时轨迹是否连续；
- 联调不依赖绝对空间位置的 TTL 与奖励功能。

临时磁铁不可直接用于正式空间实验，原因包括：

- 磁铁间距、角度或相对笼门方向不标准，会造成系统性位置和角度偏差；
- 磁铁极性或磁矩不同会改变磁场分布，可能导致尺度、旋转或 segmentation 异常；
- `Bridge offset` 只修正桥架几何，不能补偿磁铁安装误差；
- `Automatic geometry computation` 不等同于任意磁铁布局校准。

临时阶段仅以“静止较稳定、运动响应连续”为通过标准，不使用绝对 X/Y、角度和 Zone 边界作为实验量。正式实验应使用匹配设备型号的官方追踪笼，或经供应商确认的标准化磁吸垫。

> [!warning] Tracking Mat 兼容性
> 公开资料中的 `NTR000528-01` Tracking Mat 直径为 180 mm，面向旧款 standard-size cage。Large 追踪笼通常将磁铁直接集成在笼底。采购 Large 专用磁吸垫前，应向供应商确认型号、直径、方向标记及兼容性，不能默认 180 mm 型号可直接使用。[W2][W3]

## 6. Cage and Clamp 参数

| 参数                   | 配置原则                                   | 常见误区                                        |
| ---------------------- | ------------------------------------------ | ----------------------------------------------- |
| Cage type              | 与实际笼体形状一致，如 `Round`             | 形状不匹配会破坏几何模型                        |
| Cage size              | 填写实际直径，如 325 mm 或 290 mm          | 错误尺寸会造成尺度偏差                          |
| Magnets' orientation   | 标准安装优先选择 `Standard`                | 不能用于补偿桥架位置                            |
| Bridge offset          | 中心位置填 `0`；移动后填实际偏移           | 远离 air connector 为正，靠近为负               |
| Geometry computation   | 常规使用 `Automatic`                       | 无校准依据时不要手动调整几何参数                |
| Bridge orientation     | 默认安装使用 `Default`                     | `Default` 表示动物面向远离 air connector 的方向 |
| Clamp type             | 与实际夹具型号一致                         | 夹具型号会影响头固定几何                        |
| Mouse head orientation | 正常安装为 `Default`；反向应用为 `Inverse` | `Inverse` 表示动物面向桥架                      |
| Clamp rotation block   | 与是否安装 rotation block 一致             | 该选项与磁铁方向无关                            |

配置原则是先保证物理几何正确，再使软件参数与物理状态一致。磁铁方向、桥架方向、桥架偏移和鼠头方向是独立自由度，不能通过修改其他参数“补偿”错误安装。

## 7. 现场调试流程

1. ECU 断电，检查 USB 与 15-pin cable；移开附近的强磁铁和大型铁磁物体。
2. 将两块临时磁铁可靠固定，确保磁铁不会相对笼体移动。
3. 设置实际 Cage type 和 Cage size；Magnets' orientation 暂设 `Standard`；Bridge offset 使用实测值。
4. 点击 Play，先观察笼体静止时坐标是否稳定，再缓慢平移和旋转笼体。
5. 若轨迹连续但方向错误，优先检查磁铁整体方向和 Magnets' orientation。
6. 若中心整体偏移，检查桥架机械零位和 Bridge offset 的符号。
7. 主链路确认后再联调 I/O；标准磁铁安装并验收前，不进行依赖 Zone 的正式闭环实验。

## 8. 验收与排障矩阵

| 检查项            | 通过标准                           | 失败时优先检查                               |
| ----------------- | ---------------------------------- | -------------------------------------------- |
| ECU 通信          | Hardware info 正常，串口测试通过   | CP210x 驱动、USB、COM 口占用、15-pin cable   |
| 静止稳定性        | 坐标不持续大范围随机跳动           | 磁铁是否存在和固定、环境磁场、磁铁强度与极性 |
| 运动连续性        | 缓慢移动时轨迹连续                 | 磁铁固定、Cage type/size、磁场饱和或方向错误 |
| 方向一致性        | 笼门、桥架、鼠头方向与软件坐标一致 | Magnets、Bridge 和 Mouse head orientation    |
| 中心位置          | 软件中心与机械零位一致             | Bridge offset、桥架刻度、Cage size           |
| Zone segmentation | 区域边界合理且无异常跳区           | 必须先确认标准磁铁几何；临时磁铁不作正式验收 |

## 9. 使用与维护

- 不得带电插拔 ECU 与 sensor board 的连接线。
- 防止水或奖励液进入气浮平台气孔，以免堵塞气路或损坏传感板。
- 追踪磁铁应远离铁磁金属表面保存，避免吸附和笼底损伤。
- 更换正式追踪笼或磁吸垫后，重新核对 Cage size、Magnets' orientation，并执行 Timings calibration。
- 导出已验证的软件配置，并在实验日志中记录桥架刻度、笼体编号和磁铁方向。

## 10. 配置记录模板

| 项目                                 | 记录值 |
| ------------------------------------ | ------ |
| 设备型号 / ECU 序列号                |        |
| 笼体类型与直径                       |        |
| 追踪磁铁方案（内嵌 / 磁吸垫 / 临时） |        |
| 磁吸垫或磁铁方向标记                 |        |
| Bridge offset（mm）                  |        |
| Bridge orientation                   |        |
| Mouse head orientation               |        |
| Clamp type / rotation block          |        |
| Timings calibration 日期             |        |
| 软件配置文件名                       |        |

## 参考资料

- [M1] Neurotar Oy Ltd. _Mobile HomeCage® Large with Tracking Capability, User Manual 3.2.4_ (2025).
- [W1] [Neurotar — Mouse locomotion tracking](https://www.neurotar.com/support/mouse-locomotion-tracking/)
- [W2] [Neurotar — Guide to floating mouse cages](https://www.neurotar.com/support/guide-to-cages/)
- [W3] [Neurotar — Tracking mats (NTR000528-01)](https://www.neurotar.com/product/tracking-mats-set-of-six/)
