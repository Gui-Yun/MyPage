---
title: "当果蝇连接组进入 Minecraft：从展示性工程到可检验的类脑控制"
date: 2026-09-11
tags:
  - connectome
  - embodied-intelligence
  - reinforcement-learning
  - neuromorphic-computing
  - drosophila
---

# 当果蝇连接组进入 Minecraft：从展示性工程到可检验的类脑控制

最近一批项目把果蝇连接组接入 Minecraft、Beat Saber、机器人和神经形态硬件。它们很容易被描述成“果蝇大脑玩游戏”，但更准确的说法是：研究者把真实或近似真实的神经网络结构，编译成一个可运行的控制器，再为它设计感觉输入、奖励信号和动作输出。

这类工作是 AI 时代的产物。公开连接组、脉冲模拟器、游戏环境和生成式编程降低了系统集成门槛，让一个神经科学假说可以变成一个能走动、学习、犯错的数字生物。它们目前更像**可执行的机制假说和类脑工程原型**，而不是完整的果蝇仿真。

## 🧭 一张图看懂技术栈

```mermaid
flowchart LR
    accTitle: Connectome Controller Stack
    accDescr: The diagram shows how a connectome becomes a game or robot controller through sensory encoding, spiking dynamics, dopamine-modulated learning, and motor readout.

    data["FlyWire / MaleCNS\nconnectome"] --> graph["Neuron graph\n+ synapse weights"]
    graph --> dynamics["LIF / rate dynamics\nspike propagation"]
    env["Minecraft / robot\nobservation"] --> encoder["Sensory encoder\nPoisson or event spikes"]
    encoder --> dynamics
    dynamics --> readout["Motor readout\nturn, move, avoid"]
    readout --> env
    env --> reward["Reward / punishment"]
    reward --> dopamine["Dopamine-like\nmodulatory signal"]
    dopamine --> plasticity["Eligibility trace\n+ local plasticity"]
    plasticity --> graph

    classDef source fill:#dbeafe,stroke:#2563eb,color:#1e3a5f
    classDef model fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef world fill:#fef3c7,stroke:#ca8a04,color:#713f12
    class data,graph source
    class dynamics,encoder,readout,dopamine,plasticity model
    class env,reward world
```

核心闭环可以写成：

\[
\text{observation}\rightarrow\text{spikes}\rightarrow\text{connectome dynamics}\rightarrow\text{action}\rightarrow\text{reward}
\]

如果学习开启，奖励还会通过多巴胺样信号改变部分突触：

\[
\Delta w*{ij}=\eta\,\delta_t\,e*{ij}(t)
\]

其中 \(e\_{ij}\) 是资格迹，\(\delta_t\) 是奖励预测误差，\(\eta\) 是学习率。

## 🕹️ 已经出现的游戏和数字环境项目

### Ruby Project：把 FlyWire 子网络接入 Minecraft

[项目仓库](https://github.com/wavendis/ruby-project)

这是目前最接近“Minecraft 里有一只连接组果蝇”的公开项目。它使用 LIF 神经元和 FlyWire 数据，把视觉、嗅觉、机械感受、蘑菇体和运动相关神经元接在一起。Minecraft 状态先经过少量合成入口神经元，再进入连接组子网络；下行运动神经元的活动被读出为游戏中的移动。

项目还实现了 KC→MBON 的多巴胺门控可塑性：奖励事件并不是直接修改动作，而是调节与近期活动相关的突触，使数字果蝇逐步形成新的感觉—行为关联。

这个项目最值得注意的是它自己对边界的说明：神经元 ID、连接、突触权重和部分多巴胺回路来自数据；Minecraft 的感觉接口、奖励机制、学习率、速度缩放和身体动画都是人为设计的。因此它是**连接组约束的游戏控制器**，不是恢复了自然果蝇行为。

### NeuroCraft Fly：交互式 MaleCNS 网络

[项目仓库](https://github.com/evnsnclr/neurocraft-fly-public)

NeuroCraft Fly 使用 MaleCNS 重建的雄性果蝇中枢神经系统，README 给出的规模是约 166,700 个神经元和 2,558 万条有向边。它把 Minecraft 输入映射到网络活动，再从标记神经元读出行为程序。

它更像一个可视化和实验平台，而不是端到端强化学习智能体。适合做：

- 输入刺激和神经活动的可视化；
- 删除某类神经元后的行为比较；
- 真实拓扑与随机拓扑的对照；
- 将同一网络接入不同数字环境。

仓库目前仍是开发中项目，完整发行包和可复现实验资产尚在准备。它的科学价值主要来自“把结构假说变成可运行对象”，而不是已经证明了某种自然行为。

### Drosophila brain model：全脑 LIF 仿真器

[philshiu/Drosophila_brain_model](https://github.com/philshiu/Drosophila_brain_model) 是更早的基础设施型项目。它基于 FlyWire 连接数据和 Brian 2，允许按 FlyWire ID 激活或沉默神经元，输出受影响网络的 spike times 和 firing rates。

它还没有把 Minecraft 作为任务环境，但提供了游戏控制器所需的核心部件：神经元图、脉冲传播、刺激注入、神经元消融和运动通路读出。

## 🪰 真实果蝇的 VR：不是模拟脑，而是闭环实验

另一类工作让**真实果蝇**在虚拟环境中飞行或行走。果蝇不会戴 VR 头显；实验通常把它系留在球形跑步机或飞行装置上，用摄像机实时跟踪身体运动，再根据运动更新全景视觉刺激。

### FlyVR 与 FicTrac

- [Murthy Lab FlyVR](https://github.com/murthylab/fly-vr)
- [Drosophila VR FicTrac](https://github.com/renatirudy246-maker/drosophila-vr-fictrac)

典型闭环是：

```text
真实果蝇运动 → 摄像机/FicTrac → 实时估计方向和速度
                         ↓
              更新 LED 或屏幕上的虚拟场景
                         ↓
                    果蝇继续运动
```

相关研究包括 [Drosophila flying in augmented reality reveals the vision-based control of flight](https://doi.org/10.1016/j.cub.2023.12.018)。这类实验回答的是“真实果蝇如何利用视觉流控制飞行和导航”，不是“连接组模型是否能玩游戏”。

## 🔬 三类项目到底在测试什么

| 项目类型                      | 连接组的作用         | 学习信号                 | 主要问题                         |
| ----------------------------- | -------------------- | ------------------------ | -------------------------------- |
| Minecraft / Beat Saber 控制器 | 控制器骨架和稀疏先验 | 游戏奖励或人为事件       | 真实拓扑是否带来更好的任务行为？ |
| 机器人控制                    | 感觉—动作回路        | 在线奖励、模仿或固定策略 | 能否低延迟、低功耗、抗扰动？     |
| 真实果蝇 VR                   | 被研究的生物对象     | 糖、气味、光、惩罚       | 果蝇如何在闭环视觉中控制行为？   |
| 神经形态硬件                  | 稀疏事件图           | 局部三因子学习           | 能否把脉冲控制器高效部署？       |

## 🧠 为什么这些展示性工作仍然有价值

“展示性”不等于“没有科学价值”。它们的价值在于把一句机制假说变成可以运行和消融的系统：

- 删除 DAN，数字果蝇是否失去奖励记忆？
- 打乱连接但保持节点数，学习速度是否下降？
- 延迟奖励后，资格迹还能否完成信用分配？
- 同一个连接组接入网格世界、Minecraft 和机器人后，哪些行为仍然保留？
- 与同规模随机图、RNN 和 MLP 相比，真实拓扑是否提高样本效率或抗扰动能力？

只有回答这些问题，项目才从“会动的演示”进入“可检验的类脑架构研究”。

## ⚠️ 目前最容易被夸大的地方

连接组告诉我们谁和谁有突触，却没有自动给出完整的突触权重、受体状态、神经调质浓度、时间延迟和行为目标。于是一个游戏项目通常仍然包含大量人工选择：

- 哪些 Minecraft 事件算作气味、视觉或触觉；
- 哪些神经元作为动作读出；
- 什么事件产生正负奖励；
- 学习率、资格迹衰减和速度缩放是多少；
- 是否添加碰撞保护、边界约束和行为脚本。

因此最准确的表述是：

> 这些系统使用真实连接组提供结构先验，用简化神经动力学和人为设计的接口把它变成可执行控制器。

## 🧪 如果要把它做成真正的研究项目

一个小而完整的实验可以只取视觉或蘑菇体回路，接入网格世界或 Minecraft，再做三组基线：

1. 真实连接组 + 多巴胺式局部学习；
2. 相同规模的随机稀疏图 + 相同学习规则；
3. 相同参数量的 RNN/MLP + 反向传播或标准强化学习。

比较成功率之外，还应记录：

- 达到任务标准所需的交互次数；
- 奖励反转后的适应速度；
- 连接或神经元消融后的性能；
- 分布外环境中的泛化；
- 事件数、延迟和能耗。

这样才能判断优势究竟来自真实拓扑、多巴胺学习、脉冲计算，还是仅仅来自额外的人工先验。

## 📚 参考项目与论文

- [FlyWire](https://flywire.ai/)
- [FlyWire annotations](https://github.com/flyconnectome/flywire_annotations)
- [FlyWire: Online community for whole-brain connectomics](https://doi.org/10.1016/j.cell.2021.07.021)
- [Connectome-constrained networks predict neural activity across the fly visual system](https://doi.org/10.1038/s41586-024-07939-3)
- [Drosophila brain model](https://github.com/philshiu/Drosophila_brain_model)
- [Ruby Project](https://github.com/wavendis/ruby-project)
- [NeuroCraft Fly](https://github.com/evnsnclr/neurocraft-fly-public)
- [FlyVR](https://github.com/murthylab/fly-vr)
- [Drosophila VR FicTrac](https://github.com/renatirudy246-maker/drosophila-vr-fictrac)
- [Drosophila flying in augmented reality](https://doi.org/10.1016/j.cub.2023.12.018)

## 一句话总结

这波项目不是“果蝇突然学会了 Minecraft”，而是 AI 工具链第一次让我们可以把一个神经回路假说编译成数字生物、接入任意环境，再通过任务、消融和基线比较检验它到底有没有带来真正的控制优势。
