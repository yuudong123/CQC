"""Evaluate v3 on reused Test groups against simulated commercial labels."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from src.data.multiview import MultiViewDataset, load_groups
from src.data.torch_dataset import TorchMultiViewDataset
from src.data.virtual_brix import load_virtual_brix
from src.inference.commercial_policy import assess_commercial_grade, POLICY_VERSION
from src.training.engine import run_epoch
from src.training.evaluate import load_checkpoint
from src.training.models import build_model
from src.training.train import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'Refusing to overwrite: {args.output}')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    checkpoint = load_checkpoint(args.checkpoint, device)
    config = checkpoint['config']
    if config.get('target_semantics') != 'simulated_commercial_grade' or config.get('policy_version') != POLICY_VERSION:
        raise ValueError('Checkpoint is not the approved simulated-commercial target definition')
    if config.get('validation_scheme') != 'source':
        raise ValueError('Reused Test diagnostic must use the preselected source checkpoint')
    brix = load_virtual_brix(Path('data/processed/virtual-brix.csv'))
    original = [g for g in load_groups(Path('data/processed/manifest.csv'),
                                       Path('configs/splits/seed-42.csv')) if g.split == 'test']
    groups = []
    for group in original:
        synthetic = assess_commercial_grade(group.quality_grade, brix[group.group_no][0])['commercial_grade']
        if synthetic is None:
            raise ValueError(f'Missing simulated target: {group.group_no}')
        groups.append(replace(group, quality_grade=synthetic))
    source = MultiViewDataset(groups, Path('data/raw'), 12)
    model = build_model('separate_brix', pretrained=False, dropout=config['dropout']).to(device)
    model.load_state_dict(checkpoint['model_state'])
    try:
        loader = DataLoader(TorchMultiViewDataset(source, training=False, image_size=224,
                                                  virtual_brix=brix), batch_size=2, num_workers=0)
        metrics = run_epoch(model, loader, device, quality_loss_kind='focal',
                            focal_gamma=2.0, include_predictions=True)
    finally:
        source.close()
    write_json(args.output, dict(
        evaluation_role='reused_test_diagnostic_simulated_commercial_target',
        independent_final_approval=False, may_select_model_or_epoch=False,
        checkpoint=str(args.checkpoint), checkpoint_epoch=checkpoint['epoch'],
        target_semantics=config['target_semantics'], policy_version=POLICY_VERSION,
        brix_is_measured=False, test_used_for_training=False,
        target_counts=dict(Counter(g.quality_grade for g in groups)), test=metrics))
    print(f'test_groups={len(groups)} commercial_macro_f1={metrics["quality"]["macro_f1"]:.6f}', flush=True)


if __name__ == '__main__':
    main()
