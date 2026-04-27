---
title: "反卷积"
tags:
  - research-log
  - calcium-imaging
  - data-preprocessing
---

2025年12月2日 @Yun

---

## 原理和流程

钙成像技术被广泛应用于神经科学研究，通过观察钙离子的浓度变化来推断神经元的活动。在这个过程中，反卷积算法的目标是从**荧光信号（fluorescence trace）中恢复出神经元的放电（spike）**，即推断出神经元的实际活动。

反卷积的核心思想是：

荧光信号是神经元放电和钙离子动力学作用的结果。反卷积算法通过估计这些潜在的放电事件，从钙信号中恢复出神经元的活动。

---

## **反卷积的流程概述**

钙成像的反卷积通常通过**自回归（AR）模型**来建模荧光信号的时间序列。以下是反卷积算法（如 `constrained_foopsi`）的流程：

### 1. **定义自回归（AR）模型**

荧光信号是由神经元的放电活动引起的，而放电活动在时间上受到一定的钙动力学滤波作用。常用的模型是AR(1)（即每个时间点的荧光信号依赖于前一个时间点的信号）或AR(2)（即依赖于前两个时间点的信号）。这个过程可以表示为：

$$
C_t = \gamma C_{t-1} + S_t
$$

其中：

- $C_t$ 是时间 $t$ 的钙浓度或去噪后的荧光状态。
- $\gamma$ 是钙离子的衰减系数。
- $S_t$ 是神经元在时间 $t$ 的真实活动（spike）。

通过这样的自回归模型，反卷积的目标是推断出 **$S_t$**，即每个时间点的神经元放电活动。

### 2. **去卷积算法：约束优化**

反卷积算法的核心步骤是利用**约束优化**（constrained optimization）方法，从荧光信号中提取出神经元活动（spikes）。这个过程中，荧光信号经过钙动力学滤波后，反映的是**神经元放电的积分效应**，而不是单个放电的瞬时反应。因此，反卷积的关键是要解决“如何从模糊的荧光信号中恢复出原始的活动”的问题。

这个过程通常采用**最小化问题**的方式，最小化的目标是：

1. **稀疏性约束**：神经元的放电活动 $S_t$ 是稀疏的，意味着大多数时间点没有放电。因此，要求 $S_t$ 稀疏且非负。
2. **数据拟合**：荧光信号与放电活动的预测值之间的差异应当尽可能小。

反卷积算法通过迭代优化来实现这一点，通常使用 **L1 正则化** 来促进稀疏性，同时加入噪声模型来限制误差。

### 3. **信号去噪与基线估计**

在反卷积过程中，还需要**估计噪声**和**基线漂移**。因为荧光信号通常会包含**背景噪声**和**基线漂移**，这些因素需要被去除，以获得更精确的神经元活动预测。常用的去噪方法包括：

- **噪声估计**：通过估计噪声标准差 $s_n$ 来对信号进行去噪。
- **基线估计**：估计荧光信号的基线 $b$，并从信号中去除它。

### 4. **算法实现：方法概览**

```python
def constrained_foopsi(fluor, bl=None,  c1=None, g=None,  sn=None, p=None, method_deconvolution='oasis', bas_nonneg=True,
                       noise_range=[.25, .5], noise_method='logmexp', lags=5, fudge_factor=1.,
                       verbosity=False, solvers=None, optimize_g=0, s_min=None, **kwargs):
    """ Infer the most likely discretized spike train underlying a fluorescence trace

    It relies on a noise constrained deconvolution approach

    Args:
        fluor: np.ndarray
            One dimensional array containing the fluorescence intensities with
            one entry per time-bin.

        bl: [optional] float
            Fluorescence baseline value. If no value is given, then bl is estimated
            from the data.

        c1: [optional] float
            value of calcium at time 0

        g: [optional] list,float
            Parameters of the AR process that models the fluorescence impulse response.
            Estimated from the data if no value is given

        sn: float, optional
            Standard deviation of the noise distribution.  If no value is given,
            then sn is estimated from the data.

        p: int
            order of the autoregression model

        method_deconvolution: [optional] string
            solution method for basis projection pursuit 'cvx' or 'cvxpy' or 'oasis'

        bas_nonneg: bool
            baseline strictly non-negative

        noise_range:  list of two elms
            frequency range for averaging noise PSD

        noise_method: string
            method of averaging noise PSD

        lags: int
            number of lags for estimating time constants

        fudge_factor: float
            fudge factor for reducing time constant bias

        verbosity: bool
             display optimization details

        solvers: list string
            primary and secondary (if problem unfeasible for approx solution) solvers
            to be used with cvxpy, default is ['ECOS','SCS']

        optimize_g : [optional] int, only applies to method 'oasis'
            Number of large, isolated events to consider for optimizing g.
            If optimize_g=0 (default) the provided or estimated g is not further optimized.

        s_min : float, optional, only applies to method 'oasis'
            Minimal non-zero activity within each bin (minimal 'spike size').
            For negative values the threshold is abs(s_min) * sn * sqrt(1-g)
            If None (default) the standard L1 penalty is used
            If 0 the threshold is determined automatically such that RSS <= sn^2 T

    Returns:
        c: np.ndarray float
            The inferred denoised fluorescence signal at each time-bin.

        bl, c1, g, sn : As explained above

        sp: ndarray of float
            Discretized deconvolved neural activity (spikes)

        lam: float
            Regularization parameter
    Raises:
        Exception("You must specify the value of p")

        Exception('OASIS is currently only implemented for p=1 and p=2')

        Exception('Undefined Deconvolution Method')

    References:
        * Pnevmatikakis et al. 2016. Neuron, in press, http://dx.doi.org/10.1016/j.neuron.2015.11.037
        * Machado et al. 2015. Cell 162(2):338-350
    """

    if p is None:
        raise Exception("You must specify the value of p")

    if g is None or sn is None:
        # Estimate noise standard deviation and AR coefficients if they are not present
        g, sn = estimate_parameters(fluor, p=p, sn=sn, g=g, range_ff=noise_range,
                                    method=noise_method, lags=lags, fudge_factor=fudge_factor)
    lam = None
    if p == 0:
        c1 = 0
        g = np.array(0)
        bl = 0
        c = np.maximum(fluor, 0)
        sp = c.copy()

    else:  # choose a source extraction method
        if method_deconvolution == 'cvx':
            c, bl, c1, g, sn, sp = cvxopt_foopsi(
                fluor, b=bl, c1=c1, g=g, sn=sn, p=p, bas_nonneg=bas_nonneg, verbosity=verbosity)

        elif method_deconvolution == 'cvxpy':
            c, bl, c1, g, sn, sp = cvxpy_foopsi(
                fluor, g, sn, b=bl, c1=c1, bas_nonneg=bas_nonneg, solvers=solvers)

        elif method_deconvolution == 'oasis':
            from caiman.source_extraction.cnmf.oasis import constrained_oasisAR1
            penalty = 1 if s_min is None else 0
            if p == 1:
                if bl is None:
                    # Infer the most likely discretized spike train underlying an AR(1) fluorescence trace
                    # Solves the noise constrained sparse non-negative deconvolution problem
                    # min |s|_1 subject to |c-y|^2 = sn^2 T and s_t = c_t-g c_{t-1} >= 0
                    c, sp, bl, g, lam = constrained_oasisAR1(
                        fluor.astype(np.float32), g[0], sn, optimize_b=True, b_nonneg=bas_nonneg,
                        optimize_g=optimize_g, penalty=penalty, s_min=0 if s_min is None else s_min)
                else:
                    c, sp, _, g, lam = constrained_oasisAR1(
                        (fluor - bl).astype(np.float32), g[0], sn, optimize_b=False, penalty=penalty,
                        s_min=0 if s_min is None else s_min)

                c1 = c[0]

                # remove initial calcium to align with the other foopsi methods
                # it is added back in function constrained_foopsi_parallel of temporal.py
                c -= c1 * g**np.arange(len(fluor))
            elif p == 2:
                if bl is None:
                    c, sp, bl, g, lam = constrained_oasisAR2(
                        fluor.astype(np.float32), g, sn, optimize_b=True, b_nonneg=bas_nonneg,
                        optimize_g=optimize_g, penalty=penalty, s_min=s_min)
                else:
                    c, sp, _, g, lam = constrained_oasisAR2(
                        (fluor - bl).astype(np.float32), g, sn, optimize_b=False,
                        penalty=penalty, s_min=s_min)
                c1 = c[0]
                d = (g[0] + sqrt(g[0] * g[0] + 4 * g[1])) / 2
                c -= c1 * d**np.arange(len(fluor))
            else:
                raise Exception(
                    'OASIS is currently only implemented for p=1 and p=2')
            g = np.ravel(g)

        else:
            raise Exception('Undefined Deconvolution Method')

    return c, bl, c1, g, sn, sp, lam
```

下面是 `constrained_foopsi` 函数的实现流程，这个函数实现了基于 AR 模型的去卷积：

1. **参数初始化**：
   - **g**：自回归模型的参数，表示钙信号的衰减系数。
   - **sn**：噪声标准差。
   - **p**：自回归模型的阶数（通常是1或2）。
   - **b**：基线，默认通过数据估计。
2. **去卷积方法选择**：该函数支持三种去卷积方法：
   - **cvx**（通过 cvxopt 库）
   - **cvxpy**（通过 cvxpy 库）
   - **oasis**（通过 OASIS 算法）

   OASIS 是一种优化方法，专门用于处理钙成像信号中的噪声和稀疏性问题。

3. **反卷积过程**：根据选择的去卷积方法（例如 OASIS），算法会优化信号并恢复出去噪后的钙信号 $c$ 以及神经元的放电活动 $s$。
   - 通过**L1正则化**和**噪声约束**进行反卷积。
   - 同时，利用**最小二乘法**拟合荧光信号与去噪后的信号之间的差异。
4. **输出结果**：
   - **c**：去噪后的钙信号。
   - **sp**：恢复的神经元放电活动（spikes）。
   - **b**：基线漂移。
   - **g**：自回归模型的参数。
   - **sn**：噪声标准差。

### 5. **去卷积的数学模型**

去卷积的数学模型可以简化为以下优化问题：

$$
\min_{\mathbf{s}, \mathbf{c}, b} \|\mathbf{s}\|_1
\quad \text{subject to} \quad
\|\mathbf{y} - \mathbf{c} - b\mathbf{1}\|_2^2 \leq \sigma^2 T,
\quad s_t = c_t - \gamma c_{t-1} \geq 0
$$

其中：

- $\|\mathbf{s}\|_1$ 是 spike 序列的 L1 范数，用于促进稀疏性（即大部分时间点没有放电活动）。
- $\mathbf{y}$ 是观测到的荧光信号。
- $\mathbf{c}$ 是去噪后的钙信号，$b$ 是基线项。
- $s_t = c_t - \gamma c_{t-1}$ 描述 AR(1) 模型下的非负放电事件。
- $\sigma^2$ 是噪声方差，$T$ 是时间点数量。

---

## **总结：钙成像反卷积算法概述**

1. **算法目标**：从钙成像信号中推断神经元的放电活动（spikes）。
2. **核心步骤**：
   - 利用 **自回归模型（AR）** 描述信号的时间依赖性。
   - 通过 **稀疏性约束** 和 **数据拟合** 进行去卷积，恢复真实的神经元活动。
   - 使用 **噪声估计** 和 **基线去除** 来提高信号的准确性。
3. **常用方法**：
   - **OASIS** 方法用于去卷积，优化基线和钙信号衰减参数。
   - **L1 正则化** 提供稀疏性，避免过拟合。

通过这种方式，我们能够从复杂的钙成像数据中恢复出神经元的活动模式，进而分析大脑的功能和神经元之间的互动。

---

## 实际在应用在数据上的效果

## 反卷积代码

前置条件，安装CaIman

```python
# =========== 第三步 对 dF/F 进行反卷积 ==================
deconvolved_data = np.zeros_like(deltaF_over_F0)
test_sample = N

for i in range(test_sample):
    if i % 100 == 0:
        print(f"处理进度: {i}/{test_sample}")

    try:
        # 对每个神经元进行反卷积
        # p=1 对应4Hz慢信号，g会自动估计
        c, bl, c1, g, sn, sp, lam = constrained_foopsi(
            fluor=deltaF_over_F0[:, i],
            p=1,  # AR(1)模型适合慢信号
            method_deconvolution='oasis',  # 最快的方法
            optimize_g=5  # 自动优化时间常数
        )
        # 使用去卷积后的spikes
        deconvolved_data[:, i] = sp

    except Exception as e:
        print(f"神经元{i}反卷积失败: {e}")
        deconvolved_data[:, i] = deltaF_over_F0[:, i]  # 失败时保留原始dF/F
```

## 1. 前置条件：基线矫正

dF/F 矫正是相当必要的，因为基线水平会严重影响反卷积出来 spikes 的密度：

直接对原始信号做反卷积：

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image.png)

经过 dF/F 矫正后的反卷积：

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-1.png)

## 2. Trial上的形状对比

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-2.png)

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-3.png)

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-4.png)

## 3. 对后续分析的影响

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-5.png)

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-6.png)

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-7.png)

![image.png](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/image-8.png)

![img_v3_02sk_032d1b57-6dc5-4137-aa3b-ee215afa8a4g.jpg](research-logs/calcium-imaging-data-preprocessing/assets/deconvolution/img_v3_02sk_032d1b57-6dc5-4137-aa3b-ee215afa8a4g.jpg)
