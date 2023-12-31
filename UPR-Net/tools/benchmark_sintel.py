import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import math
import numpy as np
import argparse
import warnings

import torch
from torch.nn import functional as F
from torch.utils.data import DataLoader

from core.pipeline import Pipeline
from core.dataset import sintel
from core.utils.pytorch_msssim import ssim_matlab

warnings.filterwarnings("ignore")

def evaluate(ppl, data_root, batch_size, nr_data_worker=1):
    dataset = sintel(data_root=data_root)
    val_data = DataLoader(dataset, batch_size=batch_size,
            num_workers=nr_data_worker, pin_memory=True)

    psnr_list = []
    ssim_list = []
    nr_val = val_data.__len__()
    for i, data in enumerate(val_data):
        data_gpu = data[0] if isinstance(data, list) else data
        data_gpu = data_gpu.to(DEVICE, non_blocking=True) / 255.

        img0 = data_gpu[:, :3]
        img1 = data_gpu[:, 3:6]
        gt = data_gpu[:, 6:9]
        with torch.no_grad():
            pred, bi_flow, warped_img0, warped_img1, _ = ppl.inference(img0, img1, pyr_level=PYR_LEVEL)

        batch_psnr = []
        batch_ssim = []
        for j in range(gt.shape[0]):
            this_gt = gt[j]
            this_pred = pred[j]
            ssim = ssim_matlab(
                    this_pred.unsqueeze(0),
                    this_gt.unsqueeze(0)).cpu().numpy()
            ssim = float(ssim)
            ssim_list.append(ssim)
            batch_ssim.append(ssim)
            psnr = -10 * math.log10(
                    torch.mean(
                        (this_gt - this_pred) * (this_gt - this_pred)
                        ).cpu().data)
            psnr_list.append(psnr)
            batch_psnr.append(psnr)
        print('batch: {}/{}; psnr: {:.4f}; ssim: {:.4f}'.format(i, nr_val,
            np.mean(batch_psnr), np.mean(batch_ssim)))

    psnr = np.array(psnr_list).mean()
    print('average psnr: {:.4f}'.format(psnr))
    ssim = np.array(ssim_list).mean()
    print('average ssim: {:.4f}'.format(ssim))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='benchmark on sintel')

    #**********************************************************#
    # => args for dataset and data loader
    parser.add_argument('--data_root', type=str, required=True,
            help='root dir of sintel dataset')
    parser.add_argument('--batch_size', type=int, default=32,
            help='batch size for data loader')
    parser.add_argument('--nr_data_worker', type=int, default=2,
            help='number of the worker for data loader')

    #**********************************************************#
    # => args for model
    parser.add_argument('--pyr_level', type=int, default=3,
            help='the number of pyramid levels of UPR-Net in testing')

    # load version of UPR-Net
    parser.add_argument('--model_size', type=str, default="base")
    args = parser.parse_args()

    if args.model_size == 'base':
        model_file = "./checkpoints/upr-base.pkl"
    elif args.model_size == 'large':
        model_file = "./checkpoints/upr-large.pkl"
    elif args.model_size == 'Large':
        model_file = "./checkpoints/upr-llarge.pkl"
    elif args.model_size == 'att':
        model_file = "./checkpoints/upr-att.pkl"
    elif args.model_size == 'raft':
        model_file = "./checkpoints/upr-raft.pkl"
    elif args.model_size == 'softmax':
        model_file = "./checkpoints/upr-softmax.pkl"
    elif args.model_size == 'total':
        model_file = "./checkpoints/upr-total.pkl" 
    else:
        ValueError("No mactched Model Size!")

    #**********************************************************#
    # => init the benchmarking environment
    DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    torch.set_grad_enabled(False)
    if torch.cuda.is_available():
        torch.backends.cudnn.enabled = True
        torch.backends.cudnn.demo = True
    torch.backends.cudnn.benchmark = True

    #**********************************************************#
    # => init the pipeline and start to benchmark
    print('\n>>>>>>>> UPR-Net benchmark_sintel.py <<<<<<<<')
    print('\n>>>>>>>>>>>>>>>>>> Initialize <<<<<<<<<<<<<<<<<<')
    print(f"Config: {args}")

    model_cfg_dict = dict(
            load_pretrain = True,
            model_size = args.model_size,
            model_file = model_file
            )
    ppl = Pipeline(model_cfg_dict)

    # resolution-aware parameter for inference
    PYR_LEVEL = args.pyr_level

    print("benchmarking on sintel...")
    print('\n>>>>>>>>>>>>>>>>>> Evaluation <<<<<<<<<<<<<<<<<<')
    evaluate(ppl, args.data_root, args.batch_size, args.nr_data_worker)
    print('\n>>>>>>>>>>>>>>>>>> Complete <<<<<<<<<<<<<<<<<<')
