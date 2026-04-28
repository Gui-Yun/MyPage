---
title: "Liulab 第一届科研绘图设计比赛"
tags:
  - research-log
  - scientific-visualization
  - figure-design
---

2026年4月28日

---

## 背景

这件事的前因后果可能和 GPT-image 有关。老板大概是觉得在 AI 时代，绘制图像不再只是体力工作，更多是在考验审美、设计感和信息表达能力，于是心血来潮举行了一个设计比赛。

![科研绘图设计比赛通知](research-logs/assets/liulab-fig2-design/brief.png)

这个比赛其实挺有意义的，主要是因为上面的观点我很认同。当然，这本来也是我自己揣测的老板的想法。正好老板打算用我的数据，我就整理了一下提交给大家。

[Submission Statement PDF](research-logs/Liulab_Fig2_Design_Submission_Statement.pdf)

## 原版

![原版 Figure 2](research-logs/assets/liulab-fig2-design/original.png)

这张图是我自己绘制的，作为原始母版。其实我已经经过比较精心的设计，所以个人认为整体已经算是好看的了。当然也有一点敝帚自珍的成分。不过我感觉这也可能造成比赛设计不达预期：原图已经有一定完成度，修改空间并不算特别大。

但这张图还是有一些我自己也知道的缺点：

- 矩阵图和山脊图的表意有点不清楚。换言之，信息量少了点，作为示意图缺少表达重心，作为统计图也没有清晰的统计指标。
- C/D 的设计我是满意的，只需要微调。当时也是在各种展示统计指标的方式里选了一个比较优雅的设计，不过现在回看，似乎有点没有必要，毕竟我并不是特别强调分布本身。
- E 和 F 可能需要大改，最大的问题就是不够好看，尤其是 F。
- 还有一点中性的修改方向：我个人选择了比较淡、比较优雅的莫兰迪配色，但其实其他风格也可以尝试，比如我一直想试的撞色风格。

## 修改版

### A 版：莫兰迪

![A 版：莫兰迪主题](research-logs/assets/liulab-fig2-design/version-a.png)

![A 版局部说明](research-logs/assets/liulab-fig2-design/version-a-detail.png)

本轮优化主要集中在版式统一和信息表达清晰度提升：

- **A/B 面板**：整体结构基本保持不变；仅对 **B 图** 做了轻微透明度微调，以减少遮挡、提升曲线辨识度。
- **C/D 面板**：统一为同一视觉语言与尺寸体系；将两组分布横向间距压缩得更紧凑、两侧留白更均衡；移除均值之间的连线，仅保留均值与误差表示；同时统一和优化了 P 值标注的展示格式。
- **E 面板**：重新分配主图与 inset 的面积比例，优化图例排布；右下角 inset 重构为更直观的统计展示，并补充 weak-tail 部分的信息表达。
- **F 面板**：重绘为与 C/D/E 一致的云雨图风格，并补充显著性比较标注，使组间差异更直观。

### B 版：撞色

![B 版：撞色主题](research-logs/assets/liulab-fig2-design/version-b.png)

在不覆盖 A 版的前提下，新增了一版**撞色主题**作为对照。选择撞色方案的动机是：莫兰迪配色稳定、低风险、整体比较“人畜无害”；而撞色具有更强视觉冲击力，更依赖配色设计与审美控制，但在强调关键对比时更有表现力。

撞色版色卡：

- Divergent: `#00B3FF`
- Convergent: `#FF006E`
- Random: `#FFBE0B`
- Coherent: `#3A86FF`
- Weak-edge FC (F 图): `#8338EC`
- Shuffle (F 图): `#FFBE0B`
