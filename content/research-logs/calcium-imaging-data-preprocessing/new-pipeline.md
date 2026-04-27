---
title: "New Calcium Imaging Pipeline"
tags:
  - research-log
  - calcium-imaging
  - data-preprocessing
---

2025年12月2日 @Yun

---

[pipeline.py](code/pipeline.py)

### 1. Stage 1: 神经元位置探测 (Neuron location probing)

- **目标**：得到一张极其清晰的、包含神经元位置信息的“地图”（STD Map）。
- **动作**：
  - 启动 `readimg_thread` (读图) 和 `pre_thread` (预处理)。
  - 启动线程池 `vds_executor`，疯狂运行 `batch_vds_frames`。
  - 这里会跑完所有数据（或者经过下采样的数据），计算出每个 Block 的 STD 投影。

### 2. Stage 2: 静态 3D 重构 (3D reconstruction of neuron locations)

- **目标**：把 2D 的 STD 地图变成 3D 的。
- **动作**：
  - 取出 Stage 1 算好的 2D STD 图。
  - `preDAO`：校正微透镜阵列的物理畸变。
  - `AIRecon`：用神经网络把 2D 图变成 3D 体积 (`.tif`)。
  - 保存结果到硬盘 (`save_std_recon_path`)。

  ```python
  # Recon STD
  # recon_logger_trt = trt.Logger(trt.Logger.ERROR)
  # with open(config['recon_model_path'], 'rb') as f, trt.Runtime(recon_logger_trt) as runtime:
  #     recon_model = runtime.deserialize_cuda_engine(f.read())
  #     recon_model = TRTModule(recon_model, input_names=['input', 'psf'], output_names=['output'])
  model_weight = torch.load(config['recon_model_path'])['model']
  recon_model = AIRecon.make(model_weight, load_sd=True).to(f'cuda:{gpus[0]}')
  recon_model.eval()
  t = time()

  std_results = []
  for block in range(35):
    save_std_path = get_std_path(
        config["save_folder"], config["proj_name"], config["site"], config["channels"][0], block + 1)
    std = stdu[block].get_std()
    add_save_task(save_buffer, save_std_path, std)
    std_results.append(std)
  ```

### 3. Stage 3: 3D 分割 (3D segmentation)

- **目标**：在 3D 地图里把神经元画出来。
- **动作**：
  - 启动进程池 `seg_executor`。
  - 并行地对 35 个 Block 运行 `seg_invoker`。
  - 结果：生成了每个神经元的坐标 Mask，并**写入共享内存**（这是为了给 Stage 4 提速）。

### 4. Stage 4: 提取时间序列 (Extracting neuron temporal activities)

- **目标**：最重要的一步，生成荧光曲线。
- **动作**：
  - **重置读图队列**：又要从头读取所有录像帧。
  - 启动 `vre_executor` (重构进程池) 和 `mp_mc_excutor` (运动校正进程池)。
  - **流水线全开**：
    1. 读图 -> 预处理 -> 写入共享内存。
    2. `mp_demotion_invoker` 从共享内存读图 -> 运动校正 -> 存回共享内存。
    3. `vre_invoker` (TensorRT) 从共享内存读图 -> **3D 重构** -> 得到 3D 体积。
    4. `mp_neuron_extract_invoker` 利用 Stage 3 的 Mask -> 在 3D 体积上**抠信号** -> 得到原始荧光值。

### 5. 后处理与数据合并 (Post-processing)

- **位置**：代码最后 100 行。
- **动作**：
  - **收集**：从队列里把所有 GPU 算出来的 Trace 拿回来。
  - **去背景**：执行公式 `Trace = Neuron - 0.24 * Neuropil`。**(这就是你之前问的步骤)**
  - **合并坐标**：把 35 个块的神经元坐标拼成全脑坐标，处理边缘重叠。
  - **保存**：
    - `global_all_neuron_trace_sub0.24.tif`: 最终的时间序列。
    - `wholebrain_output.mat`: 给 MATLAB 用的结果。
    - `merged_seg_res_global.csv`: 神经元坐标表。
    - `whole_brain_3d.tif`: 拼好的全脑 3D 图。
