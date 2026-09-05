---
title: "小鼠虚拟现实开源方案调研"
tags:
  - neuroscience
  - mouse-vr
  - open-source-hardware
  - behavioral-neuroscience
  - 3d-printing
status: "research note"
updated: 2026-09-05
---

# 小鼠虚拟现实开源方案调研

> 调研日期：2026-09-05
>
> 目标：比较小鼠 VR 方案的开源程度、材料与采购、淘宝可购性、控制难度，以及对已有 PLA 3D 打印设备的适配性。

## 一、结论摘要

如果目标是尽快搭出可运行的第一套系统，最稳妥的路线是：

**MouseGoggles 头戴式显示 + 线性跑轮，之后再升级到 3Dneuro 气浮球台。**

理由是：MouseGoggles 的软件、3D 打印件、接线、PCB 和安装说明都公开，仓库采用 MIT 许可证，官方明确推荐 FDM PLA；它不依赖曲面投影、前表面镜和复杂投影几何标定。树莓派、圆屏、ESP32、G502、泡沫球和常规机械件在淘宝基本都能找到。

如果实验重点是线性空间学习、舔舐检测、奖励阀和成像同步，可以优先考虑 **HallPassVR**。它的行为控制链比 MouseGoggles 完整，但软件组件较多，调试和长期维护更复杂。

如果目标是经典抛物面投影式 VR，**HarveyLab mouseVR** 的资料最完整，但它更像一个需要光学、机械和电子工程协同的正式平台，不适合作为低风险入门项目。

**iMRSIV** 的视场和科研验证很有吸引力，但定制镜片、精密调整台和专有光学元件使其成本及对准难度显著上升。它适合已有光机经验的实验室，不适合第一套原型。

## 二、如何判断开源

不同项目都可能被称为 open source，但开放范围差别很大。建议按下面四层判断：

1. **完整工程级开源**：有明确许可证，并同时提供机械文件、BOM、接线或 PCB、固件和实验软件。
2. **部件级开源**：只公开球台、跑轮或头固定机构，显示、奖励和实验控制需要自行整合。
3. **软件级开源**：只提供 Unity、Godot、Python 或 MATLAB 软件，硬件需要自建。
4. **资料开放但复现受限**：论文和补充文件公开，但关键镜片、PCB、专利或商业软件不可直接获得。

在这个标准下，MouseGoggles 和 HarveyLab mouseVR 最接近完整工程开源；3Dneuro 球台属于部件级开源；nctrl mouse-vr、BonVision、ViRMEn 属于软件层；Moculus 属于论文和资料开放但工程复现受限。

## 三、方案对比

| 方案 | 开源状态 | 运动或显示结构 | PLA 适配 | 国内采购 | 控制与搭建难度 |
|---|---|---|---|---|---|
| [MouseGoggles](https://github.com/sn-lab/MouseGoggles) | MIT；STL/STEP、PCB、软件、接线、装配齐全 | 树莓派 + 双圆屏 + 菲涅尔镜片；可接线性跑台或球台 | **很好**；官方明确推荐 FDM PLA | 较容易；精确光学件需核规格 | 中等，整机约 3/5 |
| [3Dneuro 球台](https://doi.org/10.5281/zenodo.4913066) | CERN-OHL-S-2.0；公开球台文件 | 气浮泡沫球；两个 Logitech G502 测运动 | **很好**；球杯需密封和打磨 | G502、阀、气泵、泡沫球、螺钉易买 | 中等，约 3/5；需自行接入 VR |
| [HallPassVR](https://github.com/GergelyTuri/HallPassVR) | GPL-3.0；硬件图纸与程序公开 | Raspberry Pi + 投影 + ESP32 + 线性跑轮 | 小支架可 PLA；跑轮主体宜亚克力 | 通用件容易；编码器和 DLP 需替代验证 | 中高，约 4/5 |
| [HarveyLab mouseVR](https://github.com/HarveyLab/mouseVR) | MIT；机械、PCB、BOM、软件齐全 | 抛物面背投 + 8 英寸气浮球 + 光流传感器 | 结构件可 PLA；球杯正式使用不建议普通 PLA | 大部分可替代；光学和传感器是瓶颈 | 高，约 5/5 |
| [iMRSIV](https://github.com/DombeckLab/IMRSIV) | GPL-3.0；STL、Zemax、Unity 工程公开 | 双目微显示 + 定制镜片 + 精密调整台 | **很好**；推荐 Tough PLA | 显示屏易买，镜片和精密台较难 | 很高，约 5/5 |
| [nctrl mouse-vr](https://github.com/nctrl-lab/mouse-vr) | Janelia Open Source License；主要是 Unity 软件 | Unity 读取球台串口，控制任务与奖励触发 | 取决于另配硬件 | 需自行采购和设计球台 | 软件中高；不是完整整机 |
| [BonVision](https://github.com/bonvision/BonVision) | MIT；通用闭环视觉软件 | Bonsai 事件流 + 外部硬件或传感器 | 不涉及机械 | Arduino、HARP 或 DAQ 另配 | 软件中等；不是现成小鼠 VR |
| [Moculus](https://doi.org/10.1038/s41592-024-02554-6) | 论文和补充文件开放；工程受定制光学和专利限制 | 微显示 + 定制 N-BK7 镜片 + 衍射相位片 | 部分结构可打印 | 关键光学件和 PCB 难 | 很高，不建议作为常规 DIY 首选 |

## 四、首选方案 MouseGoggles

### 4.1 系统结构

MouseGoggles 使用 Raspberry Pi 和 Godot 驱动两块独立 SPI 圆屏。左右眼分别渲染图像，显示屏位于菲涅尔透镜后方，头显外壳由 3D 打印件构成。跑台运动可由微控制器转换成 USB 鼠标事件，再由 Godot 映射为前进、转向或横移。

Nature Methods 论文报告了约 230° 水平、140° 垂直的组合视场和约 25° 双眼重叠。它适合视觉刺激、虚拟导航、视觉悬崖、looming stimulus，以及与海马电生理或双光子成像结合的行为任务。

### 4.2 推荐版本

- **Duo 1.9**：不需要眼动时优先考虑。结构较简单，省去相机、IR LED 和热镜。
- **EyeTrack 2.0**：需要双眼瞳孔追踪时考虑。官方当前文档明确推荐 Raspberry Pi 5、双 NoIR 相机和红外照明，但版本仍在持续更新。

### 4.3 EyeTrack 2.0 主要材料

- Raspberry Pi 5 4GB、microSD、电源；
- 1.28 英寸 240×240 SPI 圆屏 ×2；
- 焦距约 10 mm 的菲涅尔透镜 ×2；
- NoIR 微型相机 ×2；
- 近红外热镜、850 nm IR LED、电阻；
- CSI 排线、跳线、2-56 螺钉；
- Eyepiece、LensClip、CameraClip、Bracket、MirrorStencil 等打印件。

官方美国 BOM 估算约 343 美元。以淘宝兼容件估算，头显本体约 **1,200–2,500 元**；若严格使用 Thorlabs 或 Arducam 指定件，预算通常更高。此估算不含跑台、头固定、奖励液路和手术耗材。

### 4.4 PLA 打印建议

官方对 EyeTrack 2.0 的建议是：大多数精细件层高不超过 0.1 mm，Bracket 或 Mount 等承力件不超过 0.3 mm；FDM PLA 可以满足结构需求。

建议：

- 优先黑色哑光 PLA，减少杂散光；
- 镜片卡槽、相机卡扣打印后用细锉修整；
- 头显外壳可以 PLA；
- 眼动相机安装件要检查左右对称和相机近焦；
- 不要把需要高重复定位的头固定件完全依赖普通 PLA，正式成像建议金属头板和刚性支架。

## 五、3Dneuro 气浮球台

[Zenodo 记录](https://zenodo.org/records/4913066)提供球台的压缩空气支撑底座、传感器外壳和装配文件，许可证为 CERN Open Hardware Licence v2 Strongly Reciprocal。方案使用泡沫球、两个 Logitech G502 作为运动传感器，并通过球台结构测量二维运动。

### 5.1 材料

- 约 200 mm 的 EPS 泡沫球；
- FDM 打印气浮底座和传感器壳；
- Logitech G502 ×2；
- 气泵或压缩空气、阀、软管和接头；
- 螺钉、磁铁、光学平台连接件。

### 5.2 优点与风险

优点是避免了 Harvey 方案中 ADNS9800、Teensy 和定制行为 PCB 的组合；G502 光学模块和镜头关系已经固定，淘宝采购也更容易。风险是球体圆度、气压稳定性、球杯漏气和运动坐标标定。PLA 球杯可以用于样机，但内壁要打磨并用环氧或 CA 薄层封孔；长期使用建议换 PETG、ABS、PA 或玻纤尼龙。

球台本身不包含完整 VR、奖励和实验控制，因此推荐把它作为 MouseGoggles 的第二阶段运动模块。

## 六、HallPassVR 与 HarveyLab

### 6.1 HallPassVR

HallPassVR 使用 Raspberry Pi 4、两个 ESP32、旋转编码器、投影仪、亚克力圆柱跑轮和 OpenMaze PCB。软件包括 Python 图形界面、Processing 数据采集、Arduino 固件和 MATLAB 分析。

它的优势是奖励链路较完整：ESP32 可以处理编码器、舔舐输入、12 V 电磁阀、行为触发和同步输出。对应的硬件说明见 [VR electronics README](https://github.com/GergelyTuri/HallPassVR/blob/master/hardware/VR%20electronics/Readme.md)，行为板源码见 [Arduino 文件](https://github.com/GergelyTuri/HallPassVR/blob/master/software/Arduino%20code/Behavior%20board/wheel_VR_hiddenRewMultTrigRand_esp32_oneZone_1m_070124b.ino)。

缺点是组件多、版本耦合明显；README 仍将部分软件列为完善中，分析链仍依赖 MATLAB。它更适合线性空间学习，而不是需要二维自由转向的第一选择。

### 6.2 HarveyLab mouseVR

HarveyLab 方案包括：

- 抛物面背投屏；
- DLP3010 或替代投影仪；
- 前表面镜和扩散膜；
- 8 英寸空气支撑泡沫球；
- 气浮球杯和球杯底座；
- 两个 ADNS9800 光学传感器；
- Teensy 和行为 PCB；
- 舔舐检测、液体奖励和电磁阀。

官方球杯原件使用 SLS 玻纤尼龙，重视刚度、耐清洗性、气密性和内壁光滑度。普通 PLA 更适合打样和验证，不适合作为长期高频使用的最终球杯。方案的主要风险不是 CAD 文件，而是投影几何、光学焦点、运动传感增益和行为时序标定。

## 七、淘宝采购与预算

以下是 2026 年 9 月检索得到的量级估算，不是固定报价。淘宝页面经常要求登录，库存、店铺和活动价格会变化。

| 类别 | 淘宝搜索词 | 可购性与注意事项 |
|---|---|---|
| 树莓派 | `树莓派5 4GB`、`树莓派4B` | 可购性高；Pi 5 4GB 常见约 420–630 元，确认是主板还是套装 |
| 圆屏 | `GC9A01 1.28寸 240x240 圆屏 SPI` | 约 8–100 元；必须确认尺寸、排针、供电和驱动 |
| NoIR 相机 | `IMX219 NoIR`、`树莓派红外可调焦相机` | 约 36–132 元；确认 CSI 排线和微型外形 |
| 菲涅尔镜片 | `焦距10mm 菲涅尔透镜` | 通用 PMMA 很便宜，但不等同 FRP0510；焦距、直径和纹面方向要核对 |
| 光流传感器 | `ADNS3080 光流模块`、`ADNS9800 模块` | 可搜到，但芯片、镜头高度和模块固件必须台架验证 |
| G502 | `罗技 G502 Hero 有线` | 正品约 249–294 元每只；球台需两只，不要买拆机配件替代 |
| 微控制器 | `ESP32 DevKitC`、`Teensy 4.0` | ESP32 易买；Teensy 价格高且旧代码可能需要移植 |
| 液路 | `常闭微型液体电磁阀 12V`、`硅胶管`、`鲁尔接头` | 易买；要测每脉冲出水量和死体积 |
| 机架 | `2020/2040 工业铝型材`、`T型螺母` | 易买；英制 1/4-20 与公制 M6 不要混用 |
| 光学件 | `一表面镜 定制`、`热镜`、`背投膜` | 可定制；普通镜面亚克力会带来纹理和面形误差 |

粗略预算：

- MouseGoggles 头显：约 **1,200–2,500 元**；
- 3Dneuro 球台：约 **1,000–2,500 元**；
- 头显 + 球台的可运行原型：约 **2,200–5,000 元**；
- HallPassVR：约 **2,000–6,000 元**；
- HarveyLab 完整投影球方案：约 **4,000–10,000 元**，正规光机和精密光学件可能更高；
- iMRSIV：约 **20,000–60,000 元以上**。

以上均不含实验室已有电脑、光学平台、头固定手术耗材和完整奖励系统。

## 八、软件控制栈

### 8.1 推荐的分层架构

不要让 PC 或 Raspberry Pi 的游戏循环直接承担微秒到毫秒级的奖励阀和关键 TTL 时序。更稳妥的结构是：

```text
Godot / BonVision / Python
        │  高层任务、场景、状态机、日志
        ▼
Arduino / Teensy / ESP32
        │  编码器、舔舐、阀门、TTL、时间戳
        ▼
显示、奖励、成像和电生理设备
```

显示端最好增加光电二极管记录真实换帧时刻，从而测量而不是假设视觉刺激的实际出现时间。

### 8.2 软件选择

- **MouseGoggles + Godot**：头戴双目系统最直接。Godot 和仓库都是 MIT，但液体奖励通常需要另配 Arduino 或 ESP32。
- **BonVision + Bonsai**：通用闭环视觉的平衡选择。BonVision 为 MIT，可通过事件流、串口、IP、Arduino、HARP 或 Open Ephys 接入外部硬件；奖励和 TTL 仍需自行组装。
- **HallPassVR 软件栈**：行为控制链较完整，但 Python、Processing、Arduino 和 MATLAB 组合带来维护负担。
- **ViRMEn**：适合已有 MATLAB 经验的实验室。源码为 Apache-2.0，但 MATLAB 是闭源商业依赖，不能算全栈自由软件。
- **Stytra**：GPL-3.0，适合已有 Python 追踪生态；不是现成的小鼠 3D VR。
- **Unity**：渲染能力强，但 Unity 源码受专门许可约束，不属于开源引擎；不应与 Godot、MIT 仓库混为一谈。

## 九、建议的复现顺序

### 阶段 1：静态显示

先打印头显，接两块圆屏，用普通鼠标控制 Godot 场景。此阶段只验证：左右眼图像、镜片焦距、遮光、刷新率和画面畸变。

### 阶段 2：线性跑轮

加入编码器和 ESP32 或 Teensy，完成 USB HID 或串口输入。先测正负方向、运动增益、零点漂移和长时间运行稳定性。

### 阶段 3：奖励与同步

单独用微控制器控制舔舐输入、液体阀和 TTL。测量每脉冲液量、阀门延迟和相机或电生理同步误差。

### 阶段 4：二维球台

将线性跑轮替换为 3Dneuro 气浮球，逐步加入二维坐标映射、转向增益、球面摩擦校正和气压调节。

### 阶段 5：眼动和成像

最后才增加 EyeTrack 相机、IR LED、热镜、双光子或电生理。这样可以把显示、运动、奖励和成像四类故障分开定位。

## 十、主要来源

- [MouseGoggles GitHub](https://github.com/sn-lab/MouseGoggles)
- [MouseGoggles EyeTrack 2.0 BOM 与装配](https://github.com/sn-lab/MouseGoggles/blob/main/Versions/EyeTrack/2.0/Parts,%20Assembly,%20and%20Installation%20README.md)
- [MouseGoggles Nature Methods 论文](https://www.nature.com/articles/s41592-024-02540-y)
- [3Dneuro Spherical Treadmill Zenodo](https://doi.org/10.5281/zenodo.4913066)
- [HarveyLab mouseVR](https://github.com/HarveyLab/mouseVR)
- [HarveyLab 官方 BOM](https://docs.google.com/spreadsheets/d/1hkXaeRBd7GJPuhIFjeKkEIziQik9mlkZpzjhxGrkA7A/edit)
- [HallPassVR GitHub](https://github.com/GergelyTuri/HallPassVR)
- [HallPassVR 硬件电子说明](https://github.com/GergelyTuri/HallPassVR/blob/master/hardware/VR%20electronics/Readme.md)
- [iMRSIV GitHub](https://github.com/DombeckLab/IMRSIV)
- [BonVision GitHub](https://github.com/bonvision/BonVision)
- [BonVision 论文](https://doi.org/10.7554/eLife.65541)
- [ViRMEn GitHub](https://github.com/Tank-Lab/ViRMEn)
- [Moculus 论文](https://doi.org/10.1038/s41592-024-02554-6)

## 十一、实验实施提醒

头板植入、头固定、限水、舔舐奖励和红外眼照明都涉及实验动物伦理与安全评估。正式实验前应单独验证头显温升、红外照明功率、奖励制度、动物适应周期、气泵噪声和运动约束，不要把开源和已经完成动物实验验证等同起来。

