
---
title: "V1 的功能与角色重构 (Zhaoping, 2026)"
modified: 2026-04-28
tags:
  - paper-reading
  - neuroscience
---


> <span style="color: rgb(31, 31, 31)"><span style="background-color: none">Zhaoping, L. (2026). What are the functions of primary visual cortex (V1)? arXiv:2604.22716.</span></span>

### <span style="color: rgb(31, 31, 31)"><span style="background-color: none">1. 核心动机与背景</span></span>

<span style="color: rgb(31, 31, 31)"><span style="background-color: none">当前的小鼠视觉研究中，V1 常被作为一个“不会出错”的观测靶点。但作为一个拥有庞大神经元群体的初级编码器，其整体功能尚未被完全解明。随着成像技术的发展，现在的关键难点在于</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">如何清晰解耦刺激驱动、边缘计算（视网膜）、高级反馈与 V1 自身的能力</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">。</span></span>

<span style="color: rgb(31, 31, 31)"><span style="background-color: none">文章建立在一个绝对的物理约束之上：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">信息处理瓶颈</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">。大脑的代谢能量、神经元空间和计算时间均有限，仅有极少部分视觉输入（主要在注视中心）能进入最终的识别阶段。视觉系统的所有分工，本质上都是对这个瓶颈的妥协与优化。</span></span>

![\<img alt="" data-attachment-key="BEDJPLVE" data-annotation="%7B%22attachmentURI%22%3A%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FIYXDJLIU%22%2C%22annotationKey%22%3A%22VWQ5EZ7I%22%2C%22color%22%3A%22%23ffd400%22%2C%22pageLabel%22%3A%222%22%2C%22position%22%3A%7B%22pageIndex%22%3A1%2C%22rects%22%3A%5B%5B51.993%2C464.526%2C515.055%2C730.448%5D%5D%7D%2C%22citationItem%22%3A%7B%22uris%22%3A%5B%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FDUWIWZLR%22%5D%2C%22locator%22%3A%222%22%7D%7D" width="772" height="443" src="attachments/BEDJPLVE.png" ztype="zimage"> | 772](attachments/BEDJPLVE.png)\
<span class="citation" data-citation="%7B%22citationItems%22%3A%5B%7B%22uris%22%3A%5B%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FDUWIWZLR%22%5D%2C%22locator%22%3A%222%22%7D%5D%2C%22properties%22%3A%7B%7D%7D" ztype="zcitation">(<span class="citation-item"><a href="zotero://select/library/items/DUWIWZLR">Zhaoping, 2026, p. 2</a></span>)</span>

### <span style="color: rgb(31, 31, 31)"><span style="background-color: none">2. 理论框架：CPD 与 V1SH</span></span>

<span style="color: rgb(31, 31, 31)"><span style="background-color: none">为了应对上述瓶颈，作者提出了两大核心框架，重新定义了视觉处理的过程：</span></span>

*   **<span style="color: rgb(31, 31, 31)"><span style="background-color: none">中央-外围二分法 (CPD)：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> 视觉被拆分为外围视野的“观察 (Looking)”与中央视野的“看清 (Seeing)”。外围追求速度与筛选，中央追求高分辨率与精确识别。</span></span>

*   **<span style="color: rgb(31, 31, 31)"><span style="background-color: none">V1 显著性假说 (V1SH)：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> V1 不仅是特征提取器，更是引导眼跳的“运动皮层”。显著性不依赖复杂的语义解码，而是由 V1 的最高神经响应直接表征。借助</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">同特征抑制</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">，独特的局部特征（单例）能产生强烈的初始响应，形成自下而上的显著性图。</span></span>

### <span style="color: rgb(31, 31, 31)"><span style="background-color: none">3. V1 的三大核心任务</span></span>

<span style="color: rgb(31, 31, 31)"><span style="background-color: none">在 CPD 框架下，V1 的工作流被梳理为三个紧密相连的环节：</span></span>

1.  **<span style="color: rgb(31, 31, 31)"><span style="background-color: none">作为“运动皮层”引导眼跳（外围主导）：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> V1 生成显著性图并直接交由上丘 (SC) 读取，外源性地驱动眼跳。这个逻辑虽然反直觉，但在工程上是极度合理的——只有在低级脑区完成信息初筛并截断无关输入，才能真正实现对下游算力的节省。</span></span>

2.

3.  **<span style="color: rgb(31, 31, 31)"><span style="background-color: none">启动信息瓶颈：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> 从 V1 向下游脑区输出时，开始大规模剔除细节（如眼源性信息），转而传递总结性的统计数据，以此降低系统的代谢与计算负担。</span></span>

4.  **<span style="color: rgb(31, 31, 31)"><span style="background-color: none">响应反馈以支持持续识别（中央主导）：</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> 瓶颈必然导致外围视觉出现模糊、错觉与拥挤。因此，在中央视觉区域，下游脑区（如 V4）会基于有限的前馈信号 $r$ 建立假设 $H_i$，并通过自上而下的反馈向 V1 发起“查询”，索取缺失的细节 $r'$。这套</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">前馈-反馈-验证-重权衡 (FFVW)</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none"> 算法，实现了分析与合成的闭环。</span></span>

### <span style="color: rgb(31, 31, 31)"><span style="background-color: none">4. 实验与行为学印证</span></span>

<span style="color: rgb(31, 31, 31)"><span style="background-color: none">文章通过多个现象证明了反馈机制在解决“瓶颈副作用”中的关键作用。例如，</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">翻转倾斜错觉</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">与</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">反转深度错觉</span></span>**<span style="color: rgb(31, 31, 31)"><span style="background-color: none">本质上是外围视野缺乏关键信号 $r_b, r_c$ 时的错误多数投票推断。而在中央视野，大脑正是通过向 V1 查询这些被丢弃的信号来“否决”错误假设，从而消除错觉。缺乏这种反馈，就会导致视觉拥挤。</span></span>

***
![\<img alt="" data-attachment-key="KINIFDWU" data-annotation="%7B%22attachmentURI%22%3A%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FIYXDJLIU%22%2C%22annotationKey%22%3A%226G6FHMNQ%22%2C%22color%22%3A%22%23ffd400%22%2C%22pageLabel%22%3A%224%22%2C%22position%22%3A%7B%22pageIndex%22%3A3%2C%22rects%22%3A%5B%5B47.66%2C300.261%2C506.389%2C726.494%5D%5D%7D%2C%22citationItem%22%3A%7B%22uris%22%3A%5B%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FDUWIWZLR%22%5D%2C%22locator%22%3A%224%22%7D%7D" width="765" height="711" src="attachments/KINIFDWU.png" ztype="zimage"> | 765](attachments/KINIFDWU.png)\
<span class="citation" data-citation="%7B%22citationItems%22%3A%5B%7B%22uris%22%3A%5B%22http%3A%2F%2Fzotero.org%2Fusers%2F11213488%2Fitems%2FDUWIWZLR%22%5D%2C%22locator%22%3A%224%22%7D%5D%2C%22properties%22%3A%7B%7D%7D" ztype="zcitation">(<span class="citation-item"><a href="zotero://select/library/items/DUWIWZLR">Zhaoping, 2026, p. 4</a></span>)</span>
