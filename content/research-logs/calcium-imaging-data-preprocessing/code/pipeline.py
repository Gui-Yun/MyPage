# -*- coding: utf-8 -*-
'''
parallel recon(tensorrt) and save - memory load volume and stitch
'''
import copy
import os
import torch.cuda
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
from utils import *
logger = get_logger()
import uuid
import warnings
import argparse
from collections import defaultdict
from tqdm import tqdm
import tifffile as tiff
from neuron_extract.volume_neuron_extract import batch_get_neuron_energy, new_batch_get_neuron_energy
from undistort_realign.undistort_realign import block_undistort, realign_reshape, realign_merge, undistort_model_load, \
    realign_split
from VS_LFM.VS_LFM_init import init_vs_lfm, init_vs_lfm_v6
from VS_LFM.VS_LFM_infer import VS_LFM_inference
from lf_denoise.lf_denoise_main import lf_denoise_init, lf_denoise_infer
import AIRecon
from demotion import demotion
import multiprocessing
from multiprocessing import Manager
from multiprocessing.shared_memory import SharedMemory
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import queue
import concurrent.futures
import threading
import tensorrt as trt
from torch2trt import TRTModule
from hdf5storage import savemat
from std_updater import StdUpdater
# from neuron_extract.volume_neuron_extract import get_neuron_energy, get_neuronpil_mask
from neuron_extract.recon_for_neuron_extract import vs_recon_inference
from SEG_code_transfer_ori import seg_instance
from SEG_code_transfer_new_v2 import seg_instance_new
# from vs_sere_net import vs_serenet
import shutil
import hdf5storage
import pandas as pd

vsr_models = None
denoise_model = None


def init(config_path, prefix_config_path):
    cur_root = os.getcwd().replace('\\', '/') + '/reconstruction'
    scan_config_path = os.getcwd().replace('\\', '/') + '/3x3.conf.sk.png'

    logger.info("cur_root: %s" % cur_root)
    logger.info("=============== INITIALIZATION ==============")

    with open(prefix_config_path, 'r') as f:
        prefix_config = json.load(f)
    path_prefix = prefix_config["PathPrefix"]
    if config_path!='./RCConfig.json':
        config_path = path_prefix+config_path
    with open(config_path, 'r') as f:
        config = json.load(f)

    # -----------------------------------GPU setting----------------------------------
    GPUs_info = get_gpu_info(logger)
    GPU = extract_substrings_with_numbers(GPUs_info[0])[0]
    visible_gpus = config['visible_GPUs']
    # -----------------------------------project info init-----------------------------
    sequential_multi_dataset_mode = config["sequential_multi_dataset"]

    if sequential_multi_dataset_mode:
        logger.info("sequential multi-dataset mode ON")
        if len(config["input_folder"]) != len(config["proj_name"]):
            raise ValueError("the number of input_folder and proj_name must be the same")
        if isinstance(config["save_folder"],list):
            if len(config["save_folder"])>1:
                logger.warning("Only support one save folder, use the first save folder")
            config["save_folder"] = config["save_folder"][0]
        previous_DeviceNumber = None
        for inp_f,pro_n in zip(config["input_folder"],config["proj_name"]):
            if pro_n not in inp_f:
                raise ValueError("the project name must be the paired with the input folder")
            slim_path = glob.glob(path_prefix + inp_f.split('/capture')[0] + "/*.slim")[0]
            with open(slim_path, 'r') as f:
                slim = json.load(f)
            DeviceSetting = slim['DeviceSetting']
            DeviceNumber = DeviceSetting['DeviceNumber']
            previous_DeviceNumber = DeviceNumber if previous_DeviceNumber is None else previous_DeviceNumber
            if previous_DeviceNumber != DeviceNumber:
                raise ValueError("The provided multiple datasets do not appear to belong to images captured by the same device. Please check.")
            DeviceNumber = [DeviceNumber]
        proj_name = config["proj_name"]
        input_folder = []
        for inp_f in config["input_folder"]:
            input_folder.append(path_prefix + inp_f)
        save_folder = path_prefix + config["save_folder"]
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        save_folder = [save_folder]
        config["start_frame"] = [config["start_frame"]] if isinstance(config["start_frame"],int) else config["start_frame"]
        config["stop_frame"] = [config["stop_frame"]] if isinstance(config["stop_frame"],int) else config["stop_frame"]
    else:
        logger.info("independent dataset mode ON")
        legle_jugment = [isinstance(config["input_folder"],list),isinstance(config["proj_name"],list),
               isinstance(config["start_frame"],list),isinstance(config["stop_frame"],list),isinstance(config["save_folder"],list)]
        if any(legle_jugment):
            if not all(legle_jugment):
                raise ValueError("the input argument 'input_folder' and 'proj_name' and 'save_folder' and 'start_frame' and 'stop_frame' should be all list or all not list!")
            if not len(config["input_folder"])==len(config["proj_name"])==len(config["start_frame"])==len(config["stop_frame"])==len(config["save_folder"]):
                raise ValueError("the number of input_folder and proj_name and save_folder and start_frame and stop_frame must be the same")
        if not all(legle_jugment):
            config["input_folder"] = [config["input_folder"]]
            config["proj_name"] = [config["proj_name"]]
            config["start_frame"] = [config["start_frame"]]
            config["stop_frame"] = [config["stop_frame"]]
            config["save_folder"] = [config["save_folder"]]
        proj_name = config["proj_name"]
        input_folder = [path_prefix+sub_folder for sub_folder in config["input_folder"]] if isinstance(config["input_folder"],list) else path_prefix+config["input_folder"]
        save_folder = [path_prefix+sub_folder for sub_folder in config["save_folder"]] if isinstance(config["save_folder"],list) else path_prefix+config["save_folder"]
        DeviceNumber = []
        for inp_f in input_folder:
            slim_path = glob.glob(inp_f.split('/capture')[0] + "/*.slim")[0]
            with open(slim_path, 'r') as f:
                slim = json.load(f)
            DeviceSetting = slim['DeviceSetting']
            DeviceNumber.append(DeviceSetting['DeviceNumber'])
        if isinstance(save_folder,list):
            for i in range(len(save_folder)):
                if not os.path.exists(save_folder[i]):
                    os.makedirs(save_folder[i])
        else:
            if not os.path.exists(save_folder):
                os.makedirs(save_folder)


    sites = config["sites"]
    if sites is None or not isinstance(sites, list) or sites == []:
        raise Exception("the input argument 'sites' is invalid")
    site = sites[0]

    group_mode = config["group_mode"]
    if group_mode not in [0, 1]:
        raise Exception("the input argument 'group_mode' must = 0 / 1")

    channels = config["channels"]
    assert len(channels) == 1, "The number of channels must be 1"

    if channels is None or not isinstance(channels, list) or channels == []:
        raise Exception("the input argument 'channels' is invalid")

    # for channel in channels:
    #     if not os.path.exists(save_folder + '/C' + str(channel)): os.makedirs(save_folder + '/C' + str(channel))
    #     if not os.path.exists(save_folder + '/C' + str(channel) + '_MIP'): os.makedirs(save_folder + '/C' + str(channel) + '_MIP')

    start_frame, stop_frame = config["start_frame"], config["stop_frame"]

    for sub_start_frame, sub_stop_frame in zip(start_frame,stop_frame):
        if sub_start_frame > sub_stop_frame:
            raise Exception('start_frame must <= stop_frame')
    # -----------------------------------project info init-----------------------------

    # -----------------------------------realign init-----------------------------
    startX, startY = config["startX"], config["startY"]
    center_pt = [startY, startX]

    is_full_img = config["isFullImg"]
    if is_full_img == 1:
        block_gen = BlockGenerator(center_pt=center_pt)
    elif is_full_img == 2:
        # block_gen = BlockGenerator(center_pt=(667 // 2, 935 // 2), nx=159, ny=159, step_x=1905 // 15, step_y=1905 // 15,
        #                            n=1)
        # new 1x1 size
        block_gen = BlockGenerator(center_pt=(683 // 2, 945 // 2), nx=159, ny=159, step_x=1965 // 15, step_y=1965 // 15,
                                   n=1)
    else:
        block_gen = None

    scan_config = get_scan_config(scan_config_path)
    scan_config = scan_config.flatten().tolist()

    r_scan_config = np.zeros((len(scan_config),), dtype=int)

    for i in range(len(scan_config)):
        r_scan_config[scan_config[i]] = i
    r_scan_config = r_scan_config.flatten().tolist()

    # sub_x_undistorted, sub_y_undistorted = undistort_model_load(center_pt)
    # -----------------------------------realign init-----------------------------

    # -----------------------------------vsr model init-----------------------------
    if config["vsr_model"] is not None and group_mode == 1:
        vsr_model_path = cur_root + \
                         f'/source_{DeviceNumber[0]}/vsr_model/{config["vsr_model"]}.engine'
        vsr_generator_cfg = 'VS_LFM'
        global vsr_models
        vsr_models = {}
        for i in range(torch.cuda.device_count()):
            if "v6" in vsr_model_path:
                vsr_models[f'cuda:{i}'] = init_vs_lfm_v6(vsr_model_path, i)
            else:
                vsr_models[f'cuda:{i}'] = init_vs_lfm(vsr_model_path, i)
    else:
        logger.info("VSR mode OFF")
        vsr_model_path = None
        vsr_generator_cfg = 'VS_LFM'
    # -----------------------------------vsr model init-----------------------------

    # -----------------------------------denoise model init-----------------------------
    if config["denoise_model"] is not None:
        logger.info("3X3 Denoise mode ON")
        denoise_model_path = cur_root + \
                             f'/source_{DeviceNumber[0]}/denoise_model/' + config["denoise_model"]
        logger.info('denoise_model_path: %s' % denoise_model_path)
        denoise_model = lf_denoise_init(denoise_model_path, 0)
    else:
        logger.info("Denoise mode OFF")
        denoise_model_path = None
    # -----------------------------------denoise model init-----------------------------

    # -----------------------------------recon_mode init-----------------------------
    recon_mode = "AI"
    # recon_model_name = 'serenet_81v_1x1_supervised_by_3x3_61zu'
    recon_model_name = 'serenet_81v_1x1_supervised_by_3x3_61nozu'
    recon_model_path = {current_data_source_device:cur_root + f"/source_{current_data_source_device}/recon_model/" + recon_model_name + '.pth' for current_data_source_device in DeviceNumber}
    psf = []
    logger.info("Using 81 view PSF")
    if config["vsr_model"] is None and config["isFullImg"] == 2:
        config["1x1recon"] = 1
        psf_scale = 15
    else:
        config["1x1recon"] = 0
        psf_scale = 15 / 3
    # expected_psf_depth = 31 if '31' in config['psf'] else 61
    expected_psf_depth = 61
    # for i in range(35):
    #     psf.append(get_psf_shift_pt(cur_root + f"/source_{current_data_source_device}/psf/{i}", scale=psf_scale,
    #                                 depth=expected_psf_depth))
    psf = {current_data_source_device: [get_psf_shift_pt(cur_root + f"/source_{current_data_source_device}/psf/{i}", scale=psf_scale,
                                    depth=expected_psf_depth) for i in range(35)] for current_data_source_device in DeviceNumber}
    zu_flag = 1# zu infer flag
    input_views = get_input_views(recon_mode)
    sys_shiftmap = {current_data_source_device:tiff.imread(cur_root + f'/source_{current_data_source_device}/shiftmap/shiftmap_15X21.tif') for current_data_source_device in DeviceNumber}
    preDAO = config["preDAO"]
    save_mip_flag = bool(config["save_mip"])
    # -----------------------------------recon_mode init-----------------------------

    # -----------------------------------white img----------------------------------
    white_img = {}
    for current_data_source_device in DeviceNumber:
        current_data_device_white_img = []
        for i in range(35):
            white_img_path = cur_root + f'/source_{current_data_source_device}/realign/wigner_{i}.tif'
            current_data_device_white_img.append(tifffile.imread(white_img_path)[input_views])
        current_data_device_white_img = torch.tensor(np.array(current_data_device_white_img, dtype=np.float32))
        base = torch.mean(current_data_device_white_img, axis=(0, 2, 3), keepdim=True)
        current_data_device_white_img = current_data_device_white_img / base
        white_img[current_data_source_device] = current_data_device_white_img

    # -----------------------------------Demotion init-----------------------------
    temp_caiman_dir = [get_temp_caiman_dir(sub_save_folder) for sub_save_folder in save_folder]

    # -----------------------------------SEG init-----------------------------
    neuron_extract_flag = bool(config["neuron_extract"])
    seg_unet_path = cur_root + f'/source_{DeviceNumber[0]}/seg_model/{config["seg_unet"]}.pth'
    seg_exnet_path = cur_root + f'/source_{DeviceNumber[0]}/seg_model/{config["seg_exnet"]}.pth'

    # -----------------------------------batch init-----------------------------
    frames_ds_rate = config["frames_ds_rate"]
    batch_id_list = []
    sub_dataset_info = {}
    if group_mode == 0:
        wigner_id0, wigner_id1 = 9 * np.array(start_frame), 9 * np.array(stop_frame) + 8
    else:
        if sequential_multi_dataset_mode:
            tem_input_folder = input_folder.copy()
            tem_proj_name = proj_name.copy()
            sub_dataset_global_batch_index = [0,0]
            for sub_dataset_ind,(sub_dataset_folder,sub_dataset_name) in enumerate(zip(tem_input_folder,tem_proj_name)):
                sub_dataset_num = get_files_num(sub_dataset_folder,sub_dataset_name,site,channels[0])
                sub_dataset_global_batch_index = [0, sub_dataset_num-1] if sub_dataset_ind==0 else [sub_dataset_global_batch_index[1]+1, sub_dataset_global_batch_index[1]+sub_dataset_num]
                sub_dataset_info[sub_dataset_ind] = [sub_dataset_folder,sub_dataset_num, sub_dataset_global_batch_index]
                logger.info(f"sub_dataset_{sub_dataset_ind}:{sub_dataset_folder} has {sub_dataset_info[sub_dataset_ind][1]} wigners")

        wigner_id0, wigner_id1 = np.array(start_frame), np.array(stop_frame)

    total_wigner_num = wigner_id1 - wigner_id0 + 1
    for sub_dataset_total_wigner_num in total_wigner_num:
        sub_folder_batch_id_list = []
        sub_folder_batch_id_list = get_lf_ind_list(
            sub_folder_batch_id_list, False, sub_dataset_total_wigner_num, nshift=3, batch_size=72, frames_ds_rate=frames_ds_rate)
        batch_id_list.append(sub_folder_batch_id_list)
    logger.info(f"All batches: {batch_id_list}")
    # -----------------------------------batch init-----------------------------
    for sub_save_folder in save_folder:
        shutil.copy(config_path, f"{sub_save_folder}/RCConfig_bake.json")

    logger.info("========== INITIALIZATION FINISHED ==========")

    return {"sequential_multi_dataset_mode":sequential_multi_dataset_mode,
            "sub_dataset_info":sub_dataset_info,
            "proj_name": proj_name,
            "input_folder": input_folder,
            "save_folder": save_folder,
            "site": site,
            "group_mode": group_mode,
            "channels": channels,
            "start_frame": start_frame,
            "stop_frame": stop_frame,
            "is_full_img": is_full_img,
            "block_gen": block_gen,
            # "sub_x_undistorted": sub_x_undistorted,
            # "sub_y_undistorted": sub_y_undistorted,
            "white_img": white_img,
            "input_views": input_views,
            "wigner_id0": wigner_id0,
            "wigner_id1": wigner_id1,
            "batch_id_list": batch_id_list,
            "scan_config": scan_config,
            "r_scan_config": r_scan_config,
            "denoise_model_path": denoise_model_path,
            "vsr_model_path": vsr_model_path,
            "vsr_generator_cfg": vsr_generator_cfg,
            "sys_shiftmap": sys_shiftmap,  # (35,81,2)
            "psf": psf,  # 35块PSF
            "recon_model_path": recon_model_path,
            "frames_ds_rate": frames_ds_rate,
            "preDAO": preDAO,
            "1x1recon": config["1x1recon"],
            "GPU": GPU,
            "zu_flag": zu_flag,
            "save_mip_flag": save_mip_flag,
            "neuron_extract_flag": neuron_extract_flag,
            "seg_unet_path": seg_unet_path,
            "seg_exnet_path": seg_exnet_path,
            "temp_caiman_dir": temp_caiman_dir,
            "visible_gpus": visible_gpus,
            "DeviceNumber": DeviceNumber}


def preprocess(preprocess_buffer, batch_lf_stack, config, block, device, channel, batch_id, frame_count):
    '''
    preprocess_buffer: 放入preprocess完成的batch_lf_stack以及batch信息
    '''
    logger.info('----------start to process B%d T:%d-%d----------' % (block,
                                                                      config["wigner_id0"] + batch_id[0] + 1,
                                                                      config["wigner_id0"] + batch_id[1]))

    t = time()
    batch_lf_stack = block_undistort(
        batch_lf_stack, config["sub_x_undistorted"][block], config["sub_y_undistorted"][block])
    # batch_lf_stack = batch_lf_stack[:, 15:-15, 15:-15]
    logger.info('PRE: block-undistort takes: %.5f s' % (time() - t))
    # save_block_undistort_path = get_block_undistort_path(config["save_folder"], config["proj_name"], config["site"], channel, block+1, config["start_frame"] + frame_count + 1)
    # add_save_task(buffer, save_block_undistort_path, batch_lf_stack[0].to(torch.int16).cpu().numpy().astype(np.uint16))
    # batch_lf_stack = batch_lf_stack[:, 15:-15, 15:-15]
    t = time()
    batch_lf_stack = realign_reshape(
        batch_lf_stack, None)
    logger.info('PRE: realign-reshape takes: %.5f s' % (time() - t))
    save_realign_reshape_path = get_realign_reshape_path(
        config["save_folder"], config["proj_name"], config["site"], channel, block + 1,
                                                                             config["start_frame"] + frame_count + 1)
    # save_realign_folder = os.path.dirname(save_realign_reshape_path)
    # 90, 81, 159, 159
    batch_lf_stack = batch_lf_stack.cpu()
    # for i in range(batch_lf_stack.shape[0]):
    #     add_save_task(save_buffer, save_realign_folder + f"/{frame_count + i + 1}.tif",
    #                 batch_lf_stack[i,:,:,:].numpy().clip(0, 2 ** 16 - 1).astype(np.uint16))
    # add_save_task(buffer, save_realign_reshape_path, batch_lf_stack[8:].to(torch.int16).cpu().numpy().astype(np.uint16))
    # add_save_task(save_buffer, save_realign_reshape_path.replace('.tif', '_batch_CV.tif'), batch_lf_stack[:,0,:,:].numpy().clip(0, 2 ** 16 - 1).astype(np.uint16))
    batch_lf_stack = batch_lf_stack[:, config["input_views"], :, :]
    preprocess_buffer.put([block, batch_lf_stack, device,
                           channel, batch_id, frame_count])
    del batch_lf_stack
    # torch.cuda.empty_cache()


def img_read(out_buffer, config, channel, batch_id, frame_count, t_signal, sub_dataset_wigner_info_generator=None):
    '''
    out_buffer:放入读取以及分块之后的光场图以及其分块信息
    '''
    if config["is_full_img"]:
        is_multi_view = config["is_full_img"] == 2
        batch_lf_block_stack = get_lf_list_full(
            config["input_folder"], config["proj_name"], config["site"], channel, batch_id, config["wigner_id0"],logger,config["block_gen"],
            is_multi_view=is_multi_view, t_signal=t_signal, frames_ds_rate=config['frames_ds_rate'],
            sub_dataset_wigner_info_generator=sub_dataset_wigner_info_generator)
        out_buffer.put([batch_lf_block_stack, channel, batch_id, frame_count])
    else:
        for block in range(35):
            if t_signal.is_set():
                return
            batch_lf_stack = get_lf_list_2(config["input_folder"], config["proj_name"],
                                           config["site"], channel, block + 1, batch_id, config["wigner_id0"])
            out_buffer.put(
                [batch_lf_stack, channel, batch_id, frame_count, block])


def preprocess_block(preprocess_buffer, batch_lf_stack, config, block, device, channel, batch_id, frame_count):
    batch_lf_stack = torch.from_numpy(batch_lf_stack)
    # .to(device)
    preprocess(preprocess_buffer, batch_lf_stack, config, block, device,
               channel, batch_id, frame_count)


def preprocess_full(preprocess_buffer, batch_lf_block_stack, config, channel, batch_id, frame_count, t_signal,
                    mp_mc_flag=False):
    '''
    preprocess_buffer：放入分块信息以及每块的GPU分配信息，将对应块放入指定GPU调用preprocess函数进行处理
    '''
    for block in range(35):
        if t_signal.is_set():
            return
        device = 'cuda:%d' % (block % n_gpu)
        batch_lf_stack = torch.from_numpy(
            batch_lf_block_stack[block])

        if config["is_full_img"] == 2:
            if mp_mc_flag:
                batch_lf_stack = batch_lf_stack.numpy()
                shm_name = f'liqi_shm_b{block}_{uuid.uuid4()}'
                nbytes = batch_lf_stack.nbytes
                dshape = batch_lf_stack.shape
                dtype = batch_lf_stack.dtype
                # print(f'{shm_name=},prepare start')
                shm_in = SharedMemory(name=shm_name, create=True, size=nbytes)
                shm_name_dict[shm_name] = 1
                shared_array = np.ndarray(dshape, dtype=dtype, buffer=shm_in.buf)
                shared_array[:] = batch_lf_stack[:]
                # print(f'{shm_name=},prepare done')
                print(f'{block} batch {batch_id} ready for process')
                preprocess_buffer.put([block, shm_name, dshape, dtype, device, channel, batch_id, frame_count])
            else:
                # The image already has 81 views, no need to preprocess
                preprocess_buffer.put([block, batch_lf_stack, device, channel, batch_id, frame_count])
        else:
            preprocess(preprocess_buffer, batch_lf_stack, config,
                       block, device,
                       channel, batch_id, frame_count)


def batch_vds_frames(config, batch_lf_stack, block, channel, device, wigner_idx, batch_id, frame_count,current_template):
    '''
    batch_lf_stack: tensor(9, 81, 159, 159)]
    '''
    # print(f'current vds task input {batch_lf_stack.device=},{device=}')
    global vds_lock, stdu, save_buffer, demotion_lock
    bt = config["start_frame"] + frame_count + 1
    logger.info('----------START VDS B%d B-T%d----------' % (block, bt))
    # select_views = get_demotion_views(13)
    # batch_lf_stack = batch_lf_stack[:, select_views].to(device)

    t = time()
    if config["group_mode"] == 0:
        t = time()
        batch_lf_stack = realign_merge(
            batch_lf_stack, config["scan_config"], 0, 0)
        logger.info(
            f'VDS: Block {block} B-T {bt} realign-merge takes: {time() - t:.5f} s')
        # save_merge_path = get_realign_merge_path(config['save_folder'], config['proj_name'], config['site'], channel, block, bt)
        # add_save_task(save_buffer, save_merge_path, batch_lf_stack[0, :, :, :].cpu().numpy().clip(0, 2 ** 16 - 1).astype(np.uint16))
    # VS_LFM
    elif config["vsr_model_path"] is not None:
        t = time()
        # save_vsr_path = get_vsr_path(config["save_folder"], config["proj_name"], config["site"], channel, block+1, config["start_frame"] + frame_count + 1, exact=True)
        # vsr_model = init_vs_lfm(config["vsr_model_path"], device)
        # global vsr_models
        # vsr_model = vsr_model.to(device)
        # vds_lock.acquire(blocking=True)
        batch_lf_stack = VS_LFM_inference(
            vsr_models[device], batch_lf_stack, config["scan_config"], 0, device)
        # add_save_task(save_buffer, save_vsr_path,batch_lf_stack[:, 0, :, :].cpu().numpy().clip(0, 2 ** 16 - 1).astype(np.uint16))
        torch.cuda.empty_cache()
        # vds_lock.release()
        logger.info(
            f'VDS: Block {block} B-T {bt} VSR takes: {time() - t:.5f} s')

    # LF-denoising
    if config["denoise_model_path"] is not None:
        t = time()
        denoise_model = denoise_model.to(device)
        batch_lf_stack = lf_denoise_infer(
            batch_lf_stack, denoise_model[0], denoise_model[1], device)
        torch.cuda.empty_cache()
        logger.info(
            f'VDS: Block {block} B-T {bt} denoise takes: {time() - t:.5f} s')
    batch_lf_stack = batch_lf_stack.cpu().numpy()

    # Demotion
    t = time()
    # demotion_lock.acquire()
    batch_lf_stack = demotion(batch_lf_stack, block, frame_count, tag='vds', lock=demotion_lock,
                              temp_save_dir=config['temp_caiman_dir'],vds_template_dict=current_template)
    # demotion_lock.release()
    logger.info(
        f'VDS: Block {block} B-T {bt} demotion takes: {time() - t:.5f} s')

    # if config["group_mode"] == 0:
    #     t = time()
    #     batch_lf_stack = realign_split(batch_lf_stack, config["r_scan_config"])
    #     logger.info(
    #         f'VDS: Block {block} B-T {bt} realign-split takes: {time() - t:.5f} s')
    t = time()
    if stdu is not None:
        std_stack = torch.from_numpy(batch_lf_stack)
        stdu[block].add_item(std_stack,logger)
        del std_stack
    logger.info(
        f'VDS: Block {block} B-T {bt} STD takes: {time() - t:.5f} s')
    for frame in range(batch_lf_stack.shape[0]):
        frame_count += 1
        save_vsr_path = get_vsr_path(
            config["save_folder"], config["proj_name"], config["site"], channel, block + 1,
                                                                                 config["start_frame"] + frame_count)
        add_save_task(save_buffer, save_vsr_path,
                      batch_lf_stack[frame].astype(np.uint16))
    logger.info(f'VDS: Block {block} B-T {bt} save submitted')
    torch.cuda.empty_cache()
    # recon_buffer.put([block, batch_lf_stack.numpy()])


# demotion_eng_signal = manager.Event()

def mp_demotion_invoker(metadata_queue, output_queue, signal_queue, demotion_eng_signal, terminate_signal,
                        shm_name_dict,temp_caiman_save_dir='', mp_template_dict=None):
    while not (demotion_eng_signal.is_set() or terminate_signal.is_set()):
        try:
            metadata = metadata_queue.get(timeout=2)
        except:
            sleep(0.01)
            continue

        if metadata is None:
            demotion_eng_signal.set()
            metadata_queue.task_done()
            break
        try:
            block, shm_name, batch_lf_stack_shape, batch_lf_stack_dtype, device, channel, batch_id, frame_count = metadata
            # 从共享内存加载数据
            shm = SharedMemory(name=shm_name)
            input_data = np.ndarray(
                batch_lf_stack_shape,
                dtype=batch_lf_stack_dtype,
                buffer=shm.buf
            ).copy()
            shm.close()
            shm.unlink()
            del shm_name_dict[shm_name]
            tag = 'mp_mc'

            t = time()
            output = demotion(input_data, block, frame_count, tag, None, temp_save_dir=temp_caiman_save_dir, mp_template_dict=mp_template_dict)
            logger.info(f'DEMOTION: Batch {batch_id} Block {block} demotion takes: {time() - t:.5f} s')
            t = time()
            shm_out_name = shm_name + '_out'
            shm_out = SharedMemory(name=shm_out_name, create=True, size=output.nbytes)
            shm_name_dict[shm_out_name] = 1
            shared_array_out = np.ndarray(output.shape, dtype=output.dtype, buffer=shm_out.buf)
            shared_array_out[:] = output[:]
            output_queue.put([block, shm_out_name, output.shape, output.dtype, device, channel, batch_id, frame_count])
            logger.info(f'DEMOTION: Batch {batch_id} Block {block} collect res takes: {time() - t:.5f} s')

            metadata_queue.task_done()
        except:
            logger.exception(f"Error in demotion invoker")
            terminate_signal.set()
    output_queue.put(None)
    signal_queue.append(1)
    logger.info(f'{len(signal_queue)} mp_demotion_invoker exit')


# neuron_extract_eng_signal = manager.Event()
def mp_neuron_extract_invoker(batch_volume, all_block_neuron_config, batch_id, block, neuron_trace_buffer,
                              neuronpil_trace_buffer,logger):
    ## get the seg info from the sharedmemory
    t = time()
    current_block_neuron_info = all_block_neuron_config[f'block:{block}']
    shm_name_neuron_label_array = f'liqi_shm_block{block}_neuron_label'
    shm_name_neuronpil_label_array = f'liqi_shm_block{block}_neuronpil_label'
    curr_block_shm_neuron = SharedMemory(name=shm_name_neuron_label_array)
    curr_block_shm_neuronpil = SharedMemory(name=shm_name_neuronpil_label_array)
    dtype = current_block_neuron_info['dtype']
    dshape = current_block_neuron_info['dshape']
    neuron_label_array = np.ndarray(
        dshape,
        dtype=dtype,
        buffer=curr_block_shm_neuron.buf
    )
    neuronpil_label_array = np.ndarray(
        dshape,
        dtype=dtype,
        buffer=curr_block_shm_neuronpil.buf
    )
    loc_range_dict = current_block_neuron_info['loc_range_dict']
    z_start_ind = current_block_neuron_info['z_start_ind']
    z_end_ind = current_block_neuron_info['z_end_ind']

    block_neuron_traces, block_neuronpil_traces = new_batch_get_neuron_energy(neuron_label_array.transpose(2, 0, 1),
                                                                              neuronpil_label_array.transpose(2, 0, 1)
                                                                              , loc_range_dict, batch_volume,
                                                                              z_start_ind, z_end_ind)
    logger.info(f'NEURON_EXTRACT: Batch {batch_id} Block {block} trace extract takes: {time() - t:.5f} s')
    t = time()
    neuron_trace_buffer.put({f'block': block, 'batch': batch_id, 'traces': block_neuron_traces})
    neuronpil_trace_buffer.put({f'block': block, 'batch': batch_id, 'traces': block_neuronpil_traces})
    logger.info(f'NEURON_EXTRACT: Batch {batch_id} Block {block} collect res takes: {time() - t:.5f} s')

    # SharedMemory(name=shm_name_neuron_label_array).close()
    # SharedMemory(name=shm_name_neuronpil_label_array).close()


def batch_vre_frames(config, model, batch_lf_stack, block, channel, device, true_device_id, wigner_idx, batch_id,
                     frame_count, recon_background, recon_1x1_flag):
    bt = config["start_frame"] + frame_count + 1
    logger.info('----------START vre B%d B-T%d on %s----------' % (block, bt, true_device_id))

    # vs+recon+extract
    if config["preDAO"]:
        curr_shift_mesh = config["shift_mesh"][block].to(device)
    else:
        curr_shift_mesh = None
    t = time()

    batch_volume = vs_recon_inference(block, model, torch.from_numpy(batch_lf_stack).to(device),
                                      config['psf'][block].to(device),
                                      config['white_img'][block].to(device), recon_background, recon_1x1_flag, logger,
                                      shift_mesh=curr_shift_mesh, device=device, zu_flag=config['zu_flag'])

    # add_save_task(save_buffer, save_vsr_path,batch_lf_stack[:, 0, :, :].cpu().numpy().clip(0, 2 ** 16 - 1).astype(np.uint16))

    logger.info(
        f'vre: Block {block} B-T {bt} vs+recon+data_transfer takes: {time() - t:.5f} s')
    torch.cuda.empty_cache()
    return batch_volume


# terminate_signal = manager.Event()


def imgread_invoker(out_buffer, config, sub_dataset_wigner_info_generator=None):
    '''
    imread producer -> out_buffer
    '''
    global terminate_signal
    channel = config["channels"][0]
    frame_count = 0
    try:
        for batch_id in config["batch_id_list"]:  # 从分好的batchid区间中便利取出待处理原图
            if terminate_signal.is_set():
                return
            img_read(out_buffer, config, channel, batch_id, frame_count, terminate_signal, sub_dataset_wigner_info_generator)
            if config["group_mode"] == 1:
                frame_count += 72
            else:
                frame_count += 8  # 72 / 9
    except:
        logger.exception("Exception occured in imgread_invoker")
        terminate_signal.set()
    out_buffer.put(None)  # imread buffer终止信号，向后续线程传递信号


def preprocess_invoker(in_buffer, out_buffer, config, mp_mc_flag):
    '''
    preprocess producer and imread consumer: in_buffer -> out_buffer
    根据 is_full_img判断是否是整图，来分别调用preprocess_full或_preprocess_block
    '''
    global terminate_signal
    try:
        while not terminate_signal.is_set():
            # 只要有数据，就取出来
            try:
                data = in_buffer.get(timeout=2)
            except:
                sleep(0.1)
                continue
            if data is None:
                in_buffer.task_done()
                break
            if config["is_full_img"] >= 1:
                batch_lf_block_stack, channel, batch_id, frame_count = data
                preprocess_full(out_buffer, batch_lf_block_stack,
                                config, channel, batch_id, frame_count, terminate_signal, mp_mc_flag=mp_mc_flag)
            else:
                batch_lf_stack, channel, batch_id, frame_count, block = data
                preprocess_block(out_buffer, batch_lf_stack, config, block, 'cuda:%d' % (
                        block % n_gpu), channel, batch_id, frame_count)
            in_buffer.task_done()
    except:
        logger.exception("Exception occured in preprocess_invoker")
        terminate_signal.set()
    if mp_mc_flag:
        for i in range(34):
            out_buffer.put(None)
    out_buffer.put(None)  # 从in_buffer拿none跳出上述try语句，代表preprocess完所有的待处理图像，终止preprocess_invoker


vds_lock = threading.Lock()
demotion_lock = threading.Lock()


def vsr_invoker(in_buffer: queue.Queue, cuda_device,current_template):
    '''
    preprocess consumer: in_buffer(preprocess_buffer) -> vds
    '''
    torch.cuda.set_device(cuda_device)
    global vsr_end_signal, terminate_signal
    while not (terminate_signal.is_set() or vsr_end_signal):
        try:  # 从 in_buffer 队列中获取预处理结果，若队列为空则等待两秒后重试
            preprocess_res = in_buffer.get(timeout=2)
        except:
            sleep(0.1)
            continue
        if preprocess_res is None:  # 队列为空，证明consumer获取完了所有的待处理项目，则退出循环
            vsr_end_signal = True
            in_buffer.task_done()
            break
        try:  # 根据当前batch以及block分配的GPU信息，调用VDS
            block, batch_lf_stack, device, channel, batch_id, frame_count = preprocess_res
            batch_vds_frames(config, batch_lf_stack, block,
                             channel, cuda_device, 0, batch_id, frame_count,current_template)
            torch.cuda.synchronize()
        except:
            logger.exception("Error occured in vsr_invoker")
            terminate_signal.set()
        in_buffer.task_done()
    logger.info(f"VSR invorker {cuda_device} exiting")


def vre_invoker(config, model_path, output_names, in_buffer: queue.Queue, cuda_device, signal_list,
                vre_end_signal, terminate_signal, recon_background, recon_1x1_flag, batch_mip_buffer,
                mip_stitch_end_signal_list, all_block_neuron_config, neuron_trace_buffer, neuronpil_trace_buffer,shm_name_dict):
    true_device_id = cuda_device
    logger.info(f'VRE: vre_invoker {cuda_device} start')
    os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
    torch.cuda.init()  # 显式初始化CUDA
    logger_trt = trt.Logger(trt.Logger.ERROR)
    with open(model_path, 'rb') as f, trt.Runtime(logger_trt) as runtime:
        model = runtime.deserialize_cuda_engine(f.read())
    model = TRTModule(model, input_names=['input', 'psf'], output_names=output_names)
    cuda_device = 'cuda:0'
    while not (terminate_signal.is_set() or vre_end_signal.is_set()):
        try:  # 从 in_buffer 队列中获取预处理结果，若队列为空则等待两秒后重试
            preprocess_res = in_buffer.get(timeout=2)
        except:
            sleep(0.1)
            continue
        if preprocess_res is None:  # 队列为空，证明consumer获取完了所有的待处理项目，则退出循环
            if len(signal_list) == 35 and in_buffer.empty():
                logger.info(f'VRE: vre_invoker get 35 None num, all vre process done, vre exit')
                vre_end_signal.set()
                in_buffer.task_done()
                break
            in_buffer.task_done()
            continue

        try:  # 根据当前batch以及block分配的GPU信息，调用vre
            block, shm_name, dshape, dtype, device, channel, batch_id, frame_count = preprocess_res
            shm_for_vre = SharedMemory(shm_name)
            batch_lf_stack = np.ndarray(dshape, dtype=dtype, buffer=shm_for_vre.buf).copy()
            SharedMemory(shm_name).close()
            SharedMemory(shm_name).unlink()
            del shm_name_dict[shm_name]
            batch_volume = batch_vre_frames(config, model, batch_lf_stack, block,
                                            channel, cuda_device, true_device_id, 0, batch_id, frame_count,
                                            recon_background, recon_1x1_flag)
            # for ind in range(batch_volume.shape[0]):
            #     recon_volume_path = get_recon_volume_path(config["save_folder"], config["proj_name"], config["site"], config['channels'][0],block+1,batch_id[0]+ind)
            #     add_save_task(save_buffer,recon_volume_path,batch_volume[ind]/10)
            # recon_mip_save_path = get_recon_mip_path(config["save_folder"], config["proj_name"], config["site"], config["channels"][0], block + 1,batch_id)
            if config["save_mip_flag"]:
                t = time()
                batch_mip_buffer.put((batch_id, block, np.max(batch_volume[:, 15:45] / 20, axis=1).astype(np.uint16)))
                # add_save_task(save_buffer,recon_mip_save_path,np.max(batch_volume[:,15:45]/20,axis=1).astype(np.uint16))
                logger.info(f'VRE: Submitted Batch {batch_id} Block {block} MIP stitch takes {time() - t:.5f}')
            if config['neuron_extract_flag']:
                mp_neuron_extract_invoker(batch_volume, all_block_neuron_config, batch_id, block, neuron_trace_buffer,
                                          neuronpil_trace_buffer,logger)
        except:
            logger.exception("Error occured in vre_invoker")
            terminate_signal.set()
        in_buffer.task_done()
    if config["save_mip_flag"]:
        mip_stitch_end_signal_list.append(1)
        batch_mip_buffer.put(None)
    logger.info(f"vre invorker {cuda_device} exiting")

def stitch_mip_invoker(mip_buffer, mip_stitch_end_signal_list, config):
    """
    MIP拼接处理线程
    :param mip_buffer: 包含(batch_id, block, mip_data)的队列
    :param mip_stitch_end_signal_list: 拼接线程结束信号列表
    :param config: 配置信息
    """
    rows = 5
    cols = 7
    overlap = 0
    block_size = 655
    effective_size = block_size - 2 * overlap  # 有效区域尺寸

    canvas_height = rows * effective_size
    canvas_width = cols * effective_size

    # 使用字典跟踪各batch的进度
    batch_status = defaultdict(lambda: {'blocks_received': 0,
                                        'block_data': {}})

    while not (terminate_signal.is_set() or stitch_end_signal.is_set()):
        try:
            try:
                data = mip_buffer.get(timeout=2)  # 从队列中获取数据，超时2秒，防止队列为空时阻塞，线程无法退出
            except:
                sleep(0.1)
                continue
            if data is None:
                logger.info(f'STITCH: stitch_mip_invoker get {len(mip_stitch_end_signal_list)} None num')
                if len(mip_stitch_end_signal_list) == n_gpu and mip_buffer.empty():
                    logger.info(f'STITCH: stitch_mip_invoker get {n_gpu} None num, all stitch process done')
                    stitch_end_signal.set()
                    mip_buffer.task_done()
                    break
                mip_buffer.task_done()
                continue
            batch_id, block, mip = data
            logger.info(f"STITCH: Received BATCH:{batch_id} BLOCK:{block}")

            # 更新batch状态
            status = batch_status[str(batch_id)]
            status['block_data'][block] = mip
            status['blocks_received'] += 1

            # 检查是否收齐35个block
            if status['blocks_received'] == 35:
                stitched = np.zeros((mip.shape[0], canvas_height, canvas_width),
                                    dtype=mip.dtype)

                for block_idx in tqdm(range(35), desc=f'Stitching BATCH{batch_id[0]}_{batch_id[1]}'):
                    row = block_idx // cols
                    col = block_idx % cols

                    y_start = row * effective_size
                    y_end = y_start + effective_size
                    x_start = col * effective_size
                    x_end = x_start + effective_size

                    block_data = status['block_data'][block_idx]
                    stitched[:, y_start:y_end, x_start:x_end] = block_data[:, overlap:block_size - overlap,
                                                                overlap:block_size - overlap]

                # 保存路径
                save_folder = config["save_folder"] + f'/Recon_mip'
                if not os.path.exists(save_folder):
                    os.makedirs(save_folder)
                mip_save_batch = 36
                for batch_i,batch_start in enumerate(range(batch_id[0], batch_id[-1], mip_save_batch)):
                    tic_submit = time()
                    save_path = os.path.join(save_folder, f"Recon_mip_stitched_batch{batch_start}_{min(batch_start+mip_save_batch-1, batch_id[-1]-1)}.tif")
                    add_save_task(save_buffer, save_path, stitched[batch_i*mip_save_batch:min(batch_i*mip_save_batch+mip_save_batch,len(stitched))])
                logger.info(f"Submitted stitched MIP for BATCH:{batch_id}, cost:{time() - tic_submit:.5f}")

                # 清理已处理batch的状态
                del batch_status[str(batch_id)]

            mip_buffer.task_done()

        except:
            logger.exception("Error occured in stitch_mip_invoker")
            terminate_signal.set()

    # 檢查剩余未完成batch
    for bid, status in batch_status.items():
        if status['blocks_received'] > 0:
            logger.warning(f"Incomplete batch {bid} with {status['blocks_received']} blocks")


def seg_invoker(config, in_buffer: queue.Queue, cuda_device, seg_end_signal, terminate_signal, recon_rolldim_cut, SEG_save_path,
                all_block_neuron_config,radius_ratio):
    logger.info(f'SEG: seg_invoker {cuda_device} start')
    os.environ["CUDA_VISIBLE_DEVICES"] = str(cuda_device)
    torch.cuda.init()
    cuda_device = 'cuda:0'
    while not (terminate_signal.is_set() or seg_end_signal.is_set()):
        try:
            block = in_buffer.get(timeout=2)
        except:
            sleep(0.1)
            continue
        if block is None:
            seg_end_signal.set()
            in_buffer.task_done()
            break
        try:
            logger.info(f"Block {block + 1} SEG start")
            std_volume_path = get_std_recon_path(config["save_folder"], config["proj_name"], config["site"],
                                                 config["channels"][0], block + 1)

            neuron_label_array, neuronpil_label_array, seg_res_csv, loc_range_dict, z_start_ind, z_end_ind = seg_instance_new(
                std_volume_path, SEG_save_path, block,neuronpil_radius_ratio=radius_ratio, seg_unet_path=config['seg_unet_path'],
                seg_exnet_path=config['seg_exnet_path'], device=cuda_device, recon_rolldim_psf_cut=recon_rolldim_cut)

            nbytes = neuron_label_array.nbytes
            dshape = neuron_label_array.shape
            dtype = neuron_label_array.dtype

            tic = time()
            shm_name_neuron_label = f'liqi_shm_block{block}_neuron_label'
            shm_name_neuronpil_label = f'liqi_shm_block{block}_neuronpil_label'

            shm_neuron_label = SharedMemory(name=shm_name_neuron_label, create=True, size=nbytes)
            shared_array_neuron_label = np.ndarray(dshape, dtype=dtype, buffer=shm_neuron_label.buf)
            shared_array_neuron_label[:] = neuron_label_array

            shm_neuronpil_label = SharedMemory(name=shm_name_neuronpil_label, create=True, size=nbytes)
            shared_array_neuronpil_label = np.ndarray(dshape, dtype=dtype, buffer=shm_neuronpil_label.buf)
            shared_array_neuronpil_label[:] = neuronpil_label_array
            logger.info(
                f'SEG: block {block} seg mask array has been putting into the shared memory, cost: {time() - tic:.5f}s')

            all_block_neuron_config[f'block:{block}'] = {'neuron_num': len(loc_range_dict),
                                                         'loc_range_dict': loc_range_dict, 'z_start_ind': z_start_ind,
                                                         'z_end_ind': z_end_ind,
                                                         'dtype': dtype,
                                                         'dshape': dshape}

            logger.info(f"Block {block + 1} SEG finish")
        except:
            logger.exception("Error occured in seg_invoker")
            terminate_signal.set()
        in_buffer.task_done()
    logger.info(f"seg invoker {cuda_device} exiting ")


# pyinstaller --version-file file_version_info.txt ./Code/recon.py
if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    mp_context = multiprocessing.get_context('spawn')
    mp_context.Process.daemon = True
    global manager
    manager = Manager()
    global demotion_eng_signal, neuron_extract_eng_signal, terminate_signal, vre_end_signal, stitch_end_signal, seg_end_signal, shm_name_dict
    shm_name_dict = manager.dict()
    global config
    running_status = False
    logger.info("=============== PROGRAM BEGINS AT %s =============== " %
                (datetime.now()))
    warnings.filterwarnings("ignore", category=UserWarning,
                            message=".*resource_tracker.*")
    if not torch.cuda.is_available():
        raise Exception('Error: No available GPU device')
    else:
        try:
            # load config file
            parser = argparse.ArgumentParser()
            parser.add_argument('--config', default='./RCConfig.json')
            parser.add_argument('--prefix_config', default='./PathPrefix.json')
            args = parser.parse_args()
            running_status = check_process_running('recon_81_vsr_parallel.py', logger)
            if running_status:
                raise Exception('Error: Neuron extraction process is already active. Aborting.')
            all_config = init(args.config, args.prefix_config)
            for sub_config_index in range(len(all_config["save_folder"])):
                config = copy.deepcopy(all_config)
                current_device_number = config["DeviceNumber"][sub_config_index]
                config["psf"] = all_config["psf"][current_device_number]
                config["white_img"] = all_config["white_img"][current_device_number]
                config["recon_model_path"] = all_config["recon_model_path"][current_device_number]
                config["sys_shiftmap"] = all_config["sys_shiftmap"][current_device_number]
                config["input_folder"] = all_config["input_folder"][sub_config_index] if not all_config[
                    "sequential_multi_dataset_mode"] else all_config["input_folder"]
                config["save_folder"] = all_config["save_folder"][sub_config_index]
                config["proj_name"] = all_config["proj_name"][sub_config_index] if not all_config[
                    "sequential_multi_dataset_mode"] else all_config["proj_name"]
                config["batch_id_list"] = all_config["batch_id_list"][sub_config_index]
                config["wigner_id0"] = all_config["wigner_id0"][sub_config_index]
                config["wigner_id1"] = all_config["wigner_id1"][sub_config_index]
                config["temp_caiman_dir"] = all_config["temp_caiman_dir"][sub_config_index]
                config["start_frame"] = all_config["start_frame"][sub_config_index]
                config["stop_frame"] = all_config["stop_frame"][sub_config_index]

                seg_end_signal = manager.Event()
                vre_end_signal = manager.Event()
                demotion_eng_signal = manager.Event()
                neuron_extract_eng_signal = manager.Event()
                terminate_signal = manager.Event()
                stitch_end_signal = manager.Event()
                vsr_end_signal = False

                logger.info(f"[Total project number: {len(all_config['save_folder'])}, current project index: {sub_config_index+1}]") if not all_config["sequential_multi_dataset_mode"] else None
                logger.info(f"[project begin: {config['proj_name']}]") if not all_config["sequential_multi_dataset_mode"] else None

                if len(config["visible_gpus"]) == 0 or config["visible_gpus"] is None or len(
                        config["visible_gpus"]) > torch.cuda.device_count():
                    n_gpu = torch.cuda.device_count()
                    gpus = [i for i in range(n_gpu)]
                else:
                    gpus = config["visible_gpus"]
                    n_gpu = len(gpus)
                logger.info(f">>> GPU AVAILABLE {gpus}")

                #### Estimated Running Time ###
                logger.info(f"[Estimated Running Time: TotalStage: 4; "
                            f"Stage_1: {min((config['stop_frame'] - config['start_frame']) / config['frames_ds_rate'], 72) + (config['stop_frame'] - config['start_frame']) / config['frames_ds_rate'] * 2}s, Neuron location probing; "
                            f"Stage_2: 40s, 3D reconstruction of neuron locations; "
                            f"Stage_3: {250 * 8 / n_gpu}s, 3D segmentation of neuron locations; "
                            f"Stage_4: {min((config['stop_frame'] - config['start_frame']), 72) + (config['stop_frame'] - config['start_frame']) * 8 / n_gpu * 1.1 + 1477/12000000000*((config['stop_frame'] - config['start_frame'])*40000)*4}s, Extracting neuron temporal activities]")
                logger.info("Stage_1 begin")

                # initialize saving threadings
                if vsr_models is None:
                    VDS_WORKERS = 18
                else:
                    VDS_WORKERS = n_gpu

                save_buffer = manager.Queue(maxsize=VDS_WORKERS * 72)  # 最大长度为显卡数 x batch大小
                save_executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=10)
                save_exit_flag = threading.Event()
                consumer_futures = {save_executor.submit(
                    saving_task, save_buffer, save_exit_flag, f"Consumer-{i}"): i for i in range(16)}

                stdu = None
                if vsr_models is not None or config["group_mode"] == 0:
                    stdu = [StdUpdater(size=(81, 477, 477),device=f'cuda:{gpus[0]}') for _ in range(35)]
                else:
                    stdu = [StdUpdater(size=(81, 159, 159),device=f'cuda:{gpus[0]}') for _ in range(35)]

                readimg_buffer = queue.Queue(maxsize=1 if config["is_full_img"] >= 1 else 35)  # 如果整图，就坍缩为串行
                preprocess_buffer = queue.Queue(maxsize=35)  # 分35块preprocess

                current_template = {}
                vds_executor = concurrent.futures.ThreadPoolExecutor(max_workers=VDS_WORKERS,
                                                                     thread_name_prefix="VDS_worker")  # 线程池最大容量为gpu数
                vds_futures = [vds_executor.submit(
                    vsr_invoker, preprocess_buffer,f"cuda:{gpus[i % n_gpu]}",current_template) for i in range(VDS_WORKERS)]
                t_start = time()

                seq_data_generator_instance = None
                if config['sequential_multi_dataset_mode']:
                    seq_data_generator_instance = sequential_data_generator(config['input_folder'], config['proj_name'],
                                                                            config['sub_dataset_info'], config['batch_id_list'],
                                                                            frames_ds_rate=config['frames_ds_rate'])
                readimg_t = threading.Thread(target=imgread_invoker, name="Readimg_invoker",
                                             args=(readimg_buffer, config, seq_data_generator_instance), daemon=False)
                pre_t = threading.Thread(target=preprocess_invoker, name="Pre_invoker",
                                         args=(readimg_buffer, preprocess_buffer, config, False), daemon=False)

                pre_t.start()
                readimg_t.start()

                while pre_t.is_alive() or readimg_t.is_alive() or any([not f.done() for f in vds_futures]):
                    for f in vds_futures.copy():
                        if f.done():
                            f.result()
                            vds_futures.remove(f)
                    sleep(2)

                concurrent.futures.wait(vds_futures)
                # del vsr_models
                if terminate_signal.is_set():
                    logger.error("Error has occured, stop reconstructing")
                    set_finish(consumer_futures, save_exit_flag)
                    exit(-1)
                logger.info("Stage_1 done")

                logger.info("Stage_2 begin")
                logger.info("All VDS completed, reconstructing STD...")
                torch.cuda.empty_cache()
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

                #####debug reading std#############
                # std_results = []
                # for block in range(35):
                #     save_std_path = get_std_path(
                #                 config["save_folder"], config["proj_name"], config["site"], config["channels"][0], block + 1)
                #     std_results.append(tiff.imread(save_std_path))
                #############################

                config["shift_mesh"] = {}
                preDAO_mode = 'dl'
                recon_rolldim_cut = 27 if config["1x1recon"] != 1 else 0
                Si, Sj, lf_grid = None, None, None
                shiftmap = config["sys_shiftmap"]
                shiftmap = torch.from_numpy(shiftmap.astype(np.float32))  # 2,225,315
                shiftmap = shiftmap.reshape(2, 5, 3, 15, 7, 3, 15).permute(1, 4, 3, 6, 2, 5, 0)  # 5,7,15,15,3,3,2
                shiftmap = shiftmap.reshape(35, 225, 3, 3, 2)
                shiftmap = shiftmap[:, config["input_views"]]
                shiftmap = shiftmap - shiftmap[:, :, 1:2, 1:2, :]  # 35,81,3,3,2
                # shiftmap = shiftmap / 3 / 79
                shiftmap = shiftmap / 79
                shiftmap_interp = torch.zeros(35, 81, 159, 159, 2)
                for i in range(35):
                    shiftmap_interp[i] = F.interpolate(shiftmap[i].permute(0, 3, 1, 2), size=(159, 159), mode='bicubic',
                                                       align_corners=True).permute(0, 2, 3, 1)
                for block in range(35):
                    torch.cuda.empty_cache()
                    std = std_results[block]
                    ##################################
                    std = torch.from_numpy(std).to(f'cuda:{gpus[0]}') # 13, 477, 477
                    psf_block = config["psf"][block].to(f'cuda:{gpus[0]}')
                    if config["preDAO"] == 1:
                        mesh = torch.stack(torch.meshgrid(torch.linspace(-1, 1, 159), torch.linspace(-1, 1, 159)),
                                           dim=-1).unsqueeze(0).to(std.device)
                        shiftmap = shiftmap_interp[block]
                        shift_mesh = mesh + shiftmap.to(std.device)
                        std = F.grid_sample(std.unsqueeze(1), shift_mesh.flip(-1), mode='bicubic',
                                            padding_mode='zeros',
                                            align_corners=True).squeeze(1)

                        # std, shift_mesh = AIRecon.dl_predao.preDAO_net(std.unsqueeze(1),None)
                        config["shift_mesh"][block] = shift_mesh.flip(-1).cpu()
                    recon_img = recon_model(std, psf_block, crop=recon_rolldim_cut).squeeze()
                    if config['zu_flag']:
                        recon_img = volume_interplate(recon_img.unsqueeze(0), target_z=300, slice=61,
                                                      current_z_slice=recon_img.shape[0])
                    # recon_img = recon_img[5:-5, 50:-50, 50:-50]#no need to cut, SEG code will cut the overlap and interp 1/3
                    # recon_img = (recon_img/recon_img.mean()*std.mean()).clamp(0, 2 ** 16 - 1)
                    recon_img = (recon_img - 32768).to(torch.int16) + 32768
                    recon_img = recon_img.cpu().numpy().view(dtype=np.uint16)
                    save_std_recon_path = get_std_recon_path(config["save_folder"], config["proj_name"], config["site"],
                                                             config["channels"][0], block + 1)
                    add_save_task(save_buffer, save_std_recon_path, recon_img)
                    torch.cuda.empty_cache()
                    logger.info(f"Block {block + 1} STD recon save submitted")
                    logger.info(f"STD recon takes {time() - t:.5f}s")
                del std, psf_block, recon_model
                torch.cuda.empty_cache()
                logger.info("Stage_2 done")
                logger.info("=============== FINISHED AT %s total: %.1f s================" % (
                    datetime.now(), time() - t_start))

                # ================================================================================================
                # test to continue with the SEG and neuron extract progress
                logger.info("=============== Neuron Extract start AT %s ================" % (datetime.now()))
                logger.info("Stage_3 begin")
                global_tic = time()
                SEG_start = time()
                # all_block_neuron_config = {}
                all_block_neuron_label_dict = {}
                all_block_neuronpil_label_dict = {}
                all_block_neuron_config = manager.dict()
                all_block_neuron_traces = {}
                all_block_neuronpil_traces = {}
                radius_ratio = 1.2  # neuronpil and neuron radius ratio
                # recon_background = 500
                recon_background = 0
                sub_neuronpil_rate = 0.24

                std_volume_path = get_std_recon_path(config["save_folder"], config["proj_name"], config["site"],
                                                     config["channels"][0], block + 1)
                SEG_save_path = config["save_folder"] + '/SEG_res'
                os.makedirs(SEG_save_path, exist_ok=True)
                save_dir = f"{config['save_folder']}/online_radratio{radius_ratio}_sub_background{recon_background}_sub_neuronpil{sub_neuronpil_rate}"
                os.makedirs(save_dir, exist_ok=True)

                # # load from previous result for debug
                # all_block_neuron_config = torch.load(f'{save_dir}/all_block_neuron_config.pth')

                if config['neuron_extract_flag']:
                    ######################################multi process##################################
                    blocks_queue = manager.Queue()
                    for block in range(35):
                        blocks_queue.put(block)
                    blocks_queue.put(None)
                    SEG_WORKERS = n_gpu
                    seg_executor = concurrent.futures.ProcessPoolExecutor(max_workers=SEG_WORKERS,mp_context=mp_context)  # 线程池最大容量为gpu数
                    seg_futures = [seg_executor.submit(seg_invoker, config, blocks_queue, gpus[i], seg_end_signal, terminate_signal,
                                                       recon_rolldim_cut, SEG_save_path, all_block_neuron_config,radius_ratio) for i in range(SEG_WORKERS)]
                    concurrent.futures.wait(seg_futures)
                    seg_executor.shutdown(wait=True)
                    logger.info(f"SEG takes {time() - SEG_start}")
                logger.info("Stage_3 done")

                logger.info("Stage_4 begin")
                # 边重建边提取
                online_extract_flag = True
                # 时序下采样10倍之后神经分割结果
                volume_dir = None

                global recon_1x1_flag
                recon_1x1_flag = bool(config['1x1recon'])
                if recon_1x1_flag:
                    vs_sere_net_path = config['recon_model_path'].replace('.pth',
                                                                          f"_dynamic_shape_{config['GPU']}_nor6000_fp16.engine")
                    # vs_sere_net_path = './reconstruction/source/recon_model/serenet_81v.pth'
                    output_names = ['output']
                else:
                    vs_sere_net_path = './reconstruction/source/recon_model/vs_serenet_81views_4090_nor6000_fp16.engine'
                    output_names = ['output', 'vs_mean_energy']

                # load all frames wigner
                config['frames_ds_rate'] = 1  # all frames read and reconstruct
                ##########
                group_mode = config["group_mode"]
                start_frame, stop_frame = config["start_frame"], config["stop_frame"]
                frames_ds_rate = config["frames_ds_rate"]
                batch_id_list = []
                if group_mode == 0:
                    wigner_id0, wigner_id1 = 9 * start_frame, 9 * stop_frame + 8
                else:
                    wigner_id0, wigner_id1 = start_frame, stop_frame
                total_wigner_num = wigner_id1 - wigner_id0 + 1
                batch_id_list = get_lf_ind_list(
                    batch_id_list, False, total_wigner_num, nshift=3, batch_size=72, frames_ds_rate=frames_ds_rate)
                logger.info(f"All batches: {batch_id_list}")
                config['batch_id_list'] = batch_id_list
                readimg_buffer = queue.Queue(
                    maxsize=1 if config["is_full_img"] >= 1 else 35)  # 读图buffer最大为一个batch的原图，确保内存中最多存放一组待处理原图
                preprocess_buffer = manager.Queue(maxsize=35)  # 分块buffer最大容量为一块整图，分35块preprocess

                ######################multi process demotion settings###########################################
                mc_processed_buffer = manager.Queue(maxsize=35 * 2)
                mp_mc_max_workers = 35
                current_template = manager.dict()
                mp_mc_signal_list = manager.list()
                ################################################################################################

                ######################multi process neuron extract settings#####################################
                mp_shared_neuron_trace_res = manager.Queue()
                mp_shared_neuronpil_trace_res = manager.Queue()
                ################################################################################################
                mip_buffer = manager.Queue(maxsize=35 * 5) if config['save_mip_flag'] else None
                mip_stitch_end_signal_list = manager.list() if config['save_mip_flag'] else None

                VS_RECON_WORKERS = n_gpu
                vre_executor = concurrent.futures.ProcessPoolExecutor(max_workers=VS_RECON_WORKERS, mp_context=mp_context)  # 线程池最大容量为gpu数
                vre_futures = [vre_executor.submit(vre_invoker, config, vs_sere_net_path, output_names, mc_processed_buffer,
                                                   gpus[i], mp_mc_signal_list, vre_end_signal, terminate_signal,
                                                   recon_background, recon_1x1_flag, mip_buffer,
                                                   mip_stitch_end_signal_list, all_block_neuron_config,
                                                   mp_shared_neuron_trace_res, mp_shared_neuronpil_trace_res,shm_name_dict)
                               for i in range(VS_RECON_WORKERS)]

                mp_mc_excutor = concurrent.futures.ProcessPoolExecutor(max_workers=mp_mc_max_workers,mp_context=mp_context)
                mp_mc_futures = [
                    mp_mc_excutor.submit(mp_demotion_invoker, preprocess_buffer, mc_processed_buffer, mp_mc_signal_list,
                                         demotion_eng_signal, terminate_signal, shm_name_dict, config['temp_caiman_dir'], current_template)
                    for _ in range(mp_mc_max_workers)
                ]

                t_start = time()
                seq_data_generator_instance = None
                if config['sequential_multi_dataset_mode']:
                    seq_data_generator_instance = sequential_data_generator(config['input_folder'], config['proj_name'],
                                                                            config['sub_dataset_info'],
                                                                            config['batch_id_list'],
                                                                            frames_ds_rate=config['frames_ds_rate'])
                readimg_t = threading.Thread(target=imgread_invoker, name="Readimg_invoker",
                                             args=(readimg_buffer, config, seq_data_generator_instance), daemon=False)
                pre_t = threading.Thread(target=preprocess_invoker, name="Pre_invoker",
                                         args=(readimg_buffer, preprocess_buffer, config, True), daemon=False)
                if config['save_mip_flag']:
                    stitch_thread = threading.Thread(target=stitch_mip_invoker,
                                                     args=(mip_buffer, mip_stitch_end_signal_list, config),
                                                     daemon=False)

                    stitch_thread.start()
                pre_t.start()
                readimg_t.start()

                while pre_t.is_alive() or readimg_t.is_alive() or any([not m.done() for m in mp_mc_futures]) or any(
                        [not f.done() for f in vre_futures]):
                    for m in mp_mc_futures.copy():
                        if m.done():
                            m.result()
                            mp_mc_futures.remove(m)
                    for f in vre_futures.copy():
                        if f.done():
                            f.result()
                            vre_futures.remove(f)
                    sleep(2)

                concurrent.futures.wait(mp_mc_futures)
                concurrent.futures.wait(vre_futures)
                if terminate_signal.is_set():
                    logger.error("Error has occured, stop extracting")
                    set_finish(consumer_futures, save_exit_flag)
                    exit(-1)

                if config['neuron_extract_flag']:
                    for block in range(35):
                        current_block_neuron_num = all_block_neuron_config[f'block:{block}']['neuron_num']
                        all_block_neuron_traces[f'block:{block}'] = np.zeros((current_block_neuron_num,
                                                                             config['stop_frame'] - config[
                                                                                 'start_frame'] + 1))
                        all_block_neuronpil_traces[f'block:{block}'] = np.zeros((current_block_neuron_num,
                                                                                config['stop_frame'] - config[
                                                                                     'start_frame'] + 1))
                    while (not mp_shared_neuron_trace_res.empty()):
                        neuron_res = mp_shared_neuron_trace_res.get()
                        neuron_block = neuron_res['block']  # int 0-34
                        neuron_batch = neuron_res['batch']  # list [start,end]
                        neuron_trace = neuron_res['traces']  # np.array (n,t)
                        all_block_neuron_traces[f'block:{neuron_block}'][:, neuron_batch[0]:neuron_batch[1]] = neuron_trace
                        mp_shared_neuron_trace_res.task_done()
                    while (not mp_shared_neuronpil_trace_res.empty()):
                        neuronpil_res = mp_shared_neuronpil_trace_res.get()
                        neuronpil_block = neuronpil_res['block']
                        neuronpil_batch = neuronpil_res['batch']
                        neuronpil_trace = neuronpil_res['traces']
                        all_block_neuronpil_traces[f'block:{neuronpil_block}'][:,
                        neuronpil_batch[0]:neuronpil_batch[1]] = neuronpil_trace
                        mp_shared_neuronpil_trace_res.task_done()

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

                    ######################################MERGE ALL BLOCKS CSV###################################
                    h_block_size = 655
                    w_block_size = 655
                    overlap = 0
                    csv_dir = os.path.join(config["save_folder"], 'SEG_res')
                    all_dfs = []
                    z_start_matlab = 5
                    for block in range(35):
                        row = block // 7
                        col = block % 7
                        logger.info(f'Merging: block:{block}, row:{row}, col:{col}')
                        block_h_overlap = row * overlap * 2 + overlap
                        block_w_overlap = col * overlap * 2 + overlap
                        file_path = f'{csv_dir}/B{block}/seg_res.csv'
                        # 读取文件并调整坐标
                        df = pd.read_csv(file_path)
                        if not df.empty:
                            df = df.drop(columns=['nid'])
                            df["x"] += row * h_block_size - block_h_overlap + 1
                            df["y"] += col * w_block_size - block_w_overlap + 1
                            df["z"] = df["z"] - z_start_matlab + 1
                            all_dfs.append(df)

                    # 合并所有数据
                    merged_df = pd.concat(all_dfs, ignore_index=True)
                    merged_df["x"] = merged_df["x"].clip(0, (h_block_size - 2 * overlap) * 5)
                    merged_df["y"] = merged_df["y"].clip(0, (w_block_size - 2 * overlap) * 7)
                    # matlab version res
                    numeric_df = merged_df.select_dtypes(include=[np.number])
                    merged_array = numeric_df.to_numpy()
                    savemat(os.path.join(config["save_folder"], 'wholebrain_output.mat'), {'whole_center': merged_array,
                                                                                           'whole_trace_ori': final_neuron_traces})
                    # python version res
                    merged_df_python = merged_df.copy()
                    merged_df_python["x"] = merged_df_python["x"] - 1
                    merged_df_python["y"] = merged_df_python["y"] - 1
                    merged_df_python["z"] = merged_df_python["z"] + z_start_matlab - 1
                    merged_df_python.to_csv(f"{config['save_folder']}/merged_seg_res_global.csv", index=True)
                    numeric_df_python = merged_df_python.select_dtypes(include=[np.number])
                    merged_array_python = numeric_df_python.to_numpy()
                    np.save(os.path.join(config["save_folder"], 'merged_seg_res_global.npy'), merged_array_python)

                    ######################################MERGE THE ALL BLOCKS CSV###################################

                ######################################STITCH#############################################
                logger.info(f'Stitching whole brain std volume')
                overlap = 70
                stitched_volume = np.empty((61, 655 * 5, 655 * 7))
                for block in range(1, 36):
                    row = (block - 1) // 7
                    col = (block - 1) % 7
                    h_start = row * 655
                    h_end = h_start + 655
                    w_start = col * 655
                    w_end = w_start + 655
                    stitched_volume[:, h_start:h_end, w_start:w_end] = tiff.imread(
                        os.path.join(config["save_folder"], f'STD_recon/B{block}.tif'))[:, overlap:- overlap,
                                                                       overlap: - overlap]
                add_save_task(save_buffer, os.path.join(config["save_folder"], f'whole_brain_3d.tif'),
                              stitched_volume[5:-5].astype(np.uint16))
                set_finish(consumer_futures, save_exit_flag)
                logger.info("Stage_4 done")
                logger.info(f"[project done: {config['proj_name']}]") if not all_config[
                    "sequential_multi_dataset_mode"] else None

                for b in range(35):
                    for mem_type in ['neuron_label', 'neuronpil_label']:
                        name = f'liqi_shm_block{b}_{mem_type}'
                        try:
                            shm = SharedMemory(name=name)
                            shm.close()
                            shm.unlink()
                        except FileNotFoundError:
                            pass
                for shm_name in shm_name_dict.keys():
                    try:
                        shm = SharedMemory(name=shm_name)
                        shm.close()
                        shm.unlink()
                    except FileNotFoundError:
                        pass
        except Exception as e:
            if 'demotion_eng_signal' in locals():
                demotion_eng_signal.set()
            if 'neuron_extract_end_signal' in locals():
                neuron_extract_eng_signal.set()
            if 'terminate_signal' in locals():
                terminate_signal.set()
            if 'seg_end_signal' in locals():
                seg_end_signal.set()
            if 'vre_end_signal' in locals():
                vre_end_signal.set()
            if 'stitch_end_signal' in locals():
                stitch_end_signal.set()
            logger.exception("RECONSTRUCTION STOP, TERMINATING SAVING THREAD")
            set_finish(consumer_futures, save_exit_flag) if (
                        'consumer_futures' in locals() and 'save_exit_flag' in locals()) else None
        finally:
            if running_status:
                pass
            else:
                logger.info("CLEANING THE RESOURCE")
                # 显式关闭进程池
                for b in range(35):
                    for mem_type in ['neuron_label', 'neuronpil_label']:
                        name = f'liqi_shm_block{b}_{mem_type}'
                        try:
                            shm = SharedMemory(name=name)
                            shm.close()
                            shm.unlink()
                        except FileNotFoundError:
                            pass
                for shm_name in shm_name_dict.keys():
                    try:
                        shm = SharedMemory(name=shm_name)
                        shm.close()
                        shm.unlink()
                    except FileNotFoundError:
                        pass
                mp_mc_excutor.shutdown(wait=False) if "mp_mc_excutor" in locals() else None
                vre_executor.shutdown(wait=False) if "vre_executor" in locals() else None
                logger.info("CLEANING THE RESOURCE DONE")



