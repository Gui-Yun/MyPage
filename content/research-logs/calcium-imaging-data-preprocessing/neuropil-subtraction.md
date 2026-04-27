---
title: "神经毡扣除（Neuropil Subtraction）"
tags:
  - research-log
  - calcium-imaging
  - data-preprocessing
---

## 原理和处理方式

**神经毡扣除（Neuropil Subtraction）** 是钙成像预处理中用来**去除背景“光污染”**的关键步骤。

如果不做这一步，分析得到的神经元活动往往是“虚高”的，甚至会得出错误的结论（例如认为两个原本无关的神经元具有高度相关性）。

---

### 1. 什么是“神经毡” (Neuropil)？

在显微镜下，当我们画一个圈（ROI）把神经元的胞体（Soma）圈出来时，这个圈里不仅仅只有胞体。

- **解剖学上：** 神经元的胞体周围密布着轴突、树突和胶质细胞的突起，这层纠缠在一起的复杂网络就被称为**神经毡（Neuropil）**。
- **信号上：** 这些细小的突起里也充满了钙指示剂（如 GCaMP）。当周围的其他神经元兴奋时，这层“背景网络”也会发亮。

### 2. 为什么要扣除它？（问题的来源）

即使是双光子显微镜，它的聚焦点也不是无限小的，而在Z轴上有一个延展（Point Spread Function, PSF）。

当你记录胞体信号 $F_{soma}$ 时，实际上你记录的是：

$$
F_{measured} = F_{true\_soma} + F_{contamination}
$$

这就好比你在聚会上录音（录特定人的说话声），但麦克风不可避免地录进去了周围嘈杂的背景人声（Background noise）。

**如果不扣除神经毡信号，会有两个严重后果：**

1. **虚假的相关性：** 神经毡的信号通常代表了周围一群神经元的平均活动，往往与动物的整体状态（如奔跑、惊吓）高度同步。如果不扣除，你的所有神经元看起来都在“同步放电”，但这其实只是背景在同步闪烁。
2. **信号失真：** 真实的微弱 Spike 可能会被淹没在强大的背景波动中，或者背景的波动被误认为是 Spike。

### 3. 如何操作？（算法与步骤）

Neuropil Subtraction 的标准做法通常包含两步：提取背景和数学相减。

### 第一步：提取背景信号 ($F_{neuropil}$)

通常会在胞体 ROI 的周围画一个**环形区域（Annulus / Doughnut）**。

- 这个环形区域要避开其他神经元的胞体（防止把别的细胞的信号当成背景）。
- 计算这个环形区域内的平均荧光强度，作为该时间点的背景噪声 $F_{neuropil}(t)$。

### 第二步：数学公式

修正后的信号 $F_{corrected}(t)$ 计算公式如下：

$$
F_{corrected}(t) = F_{raw\_soma}(t) - r \times F_{neuropil}(t)
$$

这里的 **r** 是一个非常关键的系数（Neuropil Contamination Ratio）。

---

### 4. 关键参数：系数 $r (r-value)$

你可能会问：_“为什么不是直接减去背景？即 r=1？”_

因为胞体本身是有体积的，它占据了大部分空间，挡住了位于它正上方或正下方的部分神经毡。所以，我们要减去的不是“100%的背景强度”，而是“泄漏进来的那一部分比例”。

- **经验值：** 在大多数双光子 GCaMP6 实验中，学术界公认的经验值是 **r = 0.7**。（这是由 Karel Svoboda 实验室在 2013 年通过实验测定得出的）。
- **动态计算：** 像 Suite2p 或 CaImAn 这样的高级软件，会通过统计学方法（如鲁棒回归）为每个 ROI 自动估算一个最佳的 r 值（通常在 0.5 到 0.8 之间）。

### 5. 直观的例子

想象两条曲线：

- **红色曲线 ($F_{soma}$):** 有很多尖峰，但基线像波浪一样起伏。
- **蓝色曲线 ($F_{neuropil}$):** 没有尖峰，但波浪起伏的形状和红色曲线的基线一模一样。

Neuropil Subtraction 就是用红色减去蓝色（乘以0.7）。

结果： 得到的曲线基线变平了（去除了波浪），剩下的就是干干净净的尖峰（真实的神经元活动）。

### 总结

1. **必要性：** 低采样率下，分辨时间上的重叠很困难，因此保证幅度的纯净度（Purity）至关重要。神经毡信号是慢速波动，很容易污染你的低频采样数据。
2. **顺序：** 正确的流程是 **Raw Data -> Motion Correction -> Neuropil Subtraction -> $\Delta F/F$ -> Deconvolution**。
3. **简单实现：** 如果你自己写代码，最简单的做法是在你的 ROI mask 周围膨胀一圈做 mask，算出 $F_{neuropil}$，然后用公式 $F_{soma} - 0.7 \times F_{neuropil}$ 即可。

## 戴组的pipeline

```python
  final_neuron_traces = []
  for block in range(35):
      neuron_traces = all_block_neuron_traces[f'block:{block}']
      neuronpil_traces = all_block_neuronpil_traces[f'block:{block}']
      nor_max_neuron = np.max(neuron_traces, 1)
      nor_max_neuron[nor_max_neuron == 0] = 1
      nor_max_neuron = nor_max_neuron[:, np.newaxis]
      nor_max_pil = np.max(neuronpil_traces, 1)
      nor_max_pil = nor_max_pil[:, np.newaxis]
      nor_max_pil[nor_max_pil == 0] = 1

      sub = neuron_traces / nor_max_neuron - sub_neuronpil_rate * neuronpil_traces / nor_max_pil
      sub = sub * nor_max_neuron
      final_neuron_traces.append(sub)
      tiff.imwrite(f"{save_dir}/block_{block}_neuron_trace_sub{sub_neuronpil_rate}.tif", sub)
  final_neuron_traces = np.concatenate(final_neuron_traces, axis=0)
  final_neuron_traces = final_neuron_traces.astype(np.float32)
  tiff.imwrite(f"{config['save_folder']}/global_all_neuron_trace_sub{sub_neuronpil_rate}.tif",
               final_neuron_traces)
  logger.info("All neuron extract completed")
  torch.cuda.empty_cache()
  logger.info(f"All neuron extract takes {time() - t_start}")
```

疑似关于负值是这一块出现的问题

## 出现负值的处理方法

补充，关于Gemini的解释：

**出现负值在神经毡扣除（Neuropil Subtraction）步骤中是非常常见的情况**，特别是在信噪比低或者背景荧光波动剧烈的数据中。

这里为你解释为什么会出现这种情况，以及在进行 dF/F 之前该如何处理。

### 1. 为什么会出现负值？

从物理上讲，荧光强度（光子数）不可能是负的。出现负值纯粹是数学计算的结果。

在这个脚本中，扣除公式是：

$$F_{corrected} = F_{raw} - 0.24 \times F_{neuropil}$$

(注：脚本里还多了一步归一化，但这不改变本质逻辑)

出现负值通常有以下原因：

1. **系数过大（Over-subtraction）**：脚本里硬编码了 `0.24` 这个系数。对于某些特定的神经元，其周围背景的渗透可能实际上只有 `0.1` 甚至更低。减多了，就变负了。
2. **基线差异**：如果神经元在静息状态下的亮度非常低（接近 0），而此时周围的神经毡因为其他神经元的活动突然变亮，减去背景后就会导致结果跌破零点。
3. **噪声波动**：光子计数本身有散粒噪声（Shot Noise）。在信号很弱的地方，随机波动减去背景后可能会偶然落到负值区间。

### 2. 负值对 dF/F 的影响

如果直接带着负值去算 dF/F，确实会出问题，主要体现在计算基线 $F_0$ 时：

$$\Delta F/F = \frac{F(t) - F_0}{F_0}$$

- **如果 $F_0$ 也是负数**：分母为负，整个 $\Delta F/F$ 的正负号会反转，完全失去物理意义。
- **如果 $F_0$ 接近 0**：结果会趋向无穷大，产生巨大的尖峰（Artifact）。

### 3. 如何解决？（标准解决方案）

你需要在**下游分析**（即拿到脚本输出的 CSV/MAT 文件后，在 MATLAB 或 Python 中）进行处理。

### 方法 A：增加偏移量 (Add Offset) —— **最推荐**

这是最简单且最稳健的方法。在计算 dF/F 之前，给整条曲线加上一个常数，使其最小值变为正数。

- **操作**：找到该神经元整条时间曲线的最小值 `min_val`。如果 `min_val < 0`，则全序列加上 `abs(min_val) + constant`（例如加上一个小的正数如 10 或 100）。
- 公式：
  $$F_{shifted}(t) = F_{corrected}(t) - \min(F_{corrected}) + C$$
- **理由**：dF/F 反映的是**相对变化量**。只要 $F(t)$ 和 $F_0$ 同时增加了相同的数值，虽然绝对的 dF/F 幅值会被压缩（分母变大了），但**信号的波形、发生时间、信噪比特征都会被完美保留**。这是学术界处理负基线的标准做法。

### 方法 B：零值截断 (Zero Clipping)

将所有小于 0 的值强制设为 0（或者一个极小的正数 epsilon）。

- **操作**：`F[F < 0] = 0`
- **缺点**：这会人为地“切平”数据的底部噪声，可能会破坏基线的统计特性，导致后续计算 $F_0$（如使用中位数或百分位数时）出现偏差。**不建议用于由于过度相减导致的大面积负值。**

### 方法 C：调整扣除系数 (Adaptive Coefficient)

既然 `0.24` 导致了负值，说明对这个特定的神经元来说，系数太大了。

- **操作**：你可以回退一步。脚本输出了 `whole_trace_ori` (神经元原始值) 吗？
  - 看代码最后，`whole_trace_ori` 存的是**已经减完**的结果。
  - **补救措施**：很遗憾，这个脚本没有直接输出未减背景的原始 Raw Trace。如果需要使用方法 C，你需要修改脚本，让它分别保存 Raw Neuron Trace 和 Neuropil Trace，然后在下游分析中动态计算系数（通常使用线性回归计算 $F_{neuron} = \alpha \cdot F_{neuropil} + \beta$）。

### 总结：

个别负值是正常的数学现象，绝对可以进行矫正。只要通过增加偏移量 (Offsetting) 确保基线 $F_0 > 0$，就可以安全地计算 dF/F，且不会影响实验结论。
