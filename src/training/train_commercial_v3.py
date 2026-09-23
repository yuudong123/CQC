"""Train simulated commercial grades, NOT original appearance grades."""
from collections import Counter
from dataclasses import replace
from pathlib import Path
import argparse
import hashlib

import torch
from torch.utils.data import DataLoader

from src.data.multiview import load_groups, MultiViewDataset
from src.data.torch_dataset import TorchMultiViewDataset
from src.data.virtual_brix import load_virtual_brix
from src.inference.commercial_policy import assess_commercial_grade, POLICY_VERSION
from src.training.models import build_model
from src.training.engine import run_epoch, save_checkpoint
from src.training.train import set_reproducibility, write_json, validation_score


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=Path('outputs/training-commercial-v3'))
    parser.add_argument('--epochs', type=int, default=25)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.epochs < 1 or args.output_dir.exists():
        parser.error('epochs must be positive and output directory must not exist')
    set_reproducibility(42)
    manifest = Path('data/processed/manifest.csv')
    splits = Path('configs/splits/seed-42.csv')
    brix_path = Path('data/processed/virtual-brix.csv')
    brix = load_virtual_brix(brix_path)
    original = [g for g in load_groups(manifest, splits) if g.split != 'test']
    groups, labels = [], []
    for group in original:
        value = brix[group.group_no][0]
        result = assess_commercial_grade(group.quality_grade, value)
        grade = result['commercial_grade']
        if grade is None:
            raise ValueError(f'No commercial target: {group.group_no}')
        groups.append(replace(group, quality_grade=grade))
        labels.append(dict(group_no=group.group_no, original_split=group.original_split,
                           appearance_grade=group.quality_grade, virtual_brix=value,
                           commercial_grade=grade, score=result['score']))
    train = [g for g in groups if g.original_split == 'train']
    validation = [g for g in groups if g.original_split == 'validation']
    counts = {name: dict(Counter(g.quality_grade for g in data))
              for name, data in [('train', train), ('validation', validation)]}
    if any(set(count) != {'L', 'M', 'S'} for count in counts.values()):
        raise ValueError(f'Each development subset needs all grades: {counts}')
    config = dict(model_version='commercial-v3-candidate', model_kind='separate_brix',
                  target_semantics='simulated_commercial_grade', policy_version=POLICY_VERSION,
                  brix_is_measured=False, views=12, image_size=224, seed=42,
                  epochs=args.epochs, batch_size=2, workers=0, dropout=0.4,
                  learning_rate=0.0003, weight_decay=0.0005, quality_loss='focal',
                  focal_gamma=2.0, train_groups=len(train), validation_groups=len(validation),
                  validation_scheme='source', view_sampling='fixed', test_used=False,
                  class_counts=counts, virtual_brix=str(brix_path),
                  source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (manifest, splits, brix_path)},
                  limitation='Agreement with synthetic policy targets, not measured commercial quality')
    print(config, flush=True)
    if not args.execute:
        return
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for this remote training run')
    args.output_dir.mkdir(parents=True, exist_ok=False)
    write_json(args.output_dir / 'config.json', config)
    write_json(args.output_dir / 'development-labels.json', labels)
    device = torch.device('cuda')
    sources = [MultiViewDataset(data, Path('data/raw'), 12) for data in (train, validation)]
    loaders = [DataLoader(TorchMultiViewDataset(source, training=i == 0,
                        image_size=224, virtual_brix=brix), batch_size=2,
                        shuffle=i == 0, num_workers=0,
                        generator=torch.Generator().manual_seed(42))
               for i, source in enumerate(sources)]
    model = build_model('separate_brix', pretrained=True, dropout=0.4).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0003, weight_decay=0.0005)
    history, best = [], -1.0
    try:
        for epoch in range(1, args.epochs + 1):
            print(f'epoch_start={epoch}/{args.epochs}', flush=True)
            train_metrics = run_epoch(model, loaders[0], device, optimizer=optimizer,
                                      quality_loss_kind='focal', focal_gamma=2.0)
            metrics = run_epoch(model, loaders[1], device, quality_loss_kind='focal', focal_gamma=2.0)
            score = validation_score(metrics)
            history.append(dict(epoch=epoch, train=train_metrics, validation=metrics, validation_score=score))
            write_json(args.output_dir / 'history.json', history)
            for name in (['last.pt', 'best.pt'] if score > best else ['last.pt']):
                save_checkpoint(args.output_dir / name, model=model, optimizer=optimizer,
                                epoch=epoch, config=config, metrics=metrics)
            best = max(best, score)
            print(f'epoch={epoch}/{args.epochs} commercial_macro_f1={metrics["quality"]["macro_f1"]:.6f}', flush=True)
    finally:
        for source in sources:
            source.close()
    write_json(args.output_dir / 'summary.json', dict(epochs_completed=len(history),
               best_validation_score=best, test_used=False, target_semantics=config['target_semantics']))


if __name__ == '__main__':
    main()
