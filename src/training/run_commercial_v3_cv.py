"""Run five isolated apple-group folds for the fixed v3 policy target."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('outputs/training-commercial-v3-cv'))
    parser.add_argument('--epochs', type=int, default=25)
    args = parser.parse_args()
    if args.epochs < 17:
        parser.error('At least 17 epochs needed for the preselected source epoch comparison')
    if args.root.exists():
        parser.error(f'Refusing to reuse output root: {args.root}')
    args.root.mkdir(parents=True)
    for fold in range(5):
        destination = args.root / f'fold-{fold}'
        print(f'cv_run={fold + 1}/5', flush=True)
        subprocess.run([sys.executable, '-m', 'src.training.train_commercial_v3',
                        '--validation-scheme', 'cv', '--cv-fold', str(fold),
                        '--epochs', str(args.epochs), '--output-dir', str(destination), '--execute'], check=True)
    rows = []
    for fold in range(5):
        history = json.loads((args.root / f'fold-{fold}' / 'history.json').read_text(encoding='utf-8'))
        selected = next(item for item in history if item['epoch'] == 17)
        rows.append(dict(fold=fold, groups=selected['validation']['samples'],
                         quality_macro_f1=selected['validation']['quality']['macro_f1'],
                         cultivar_macro_f1=selected['validation']['cultivar']['macro_f1']))
    from statistics import mean
    report = dict(evaluation_role='development_group_cv', fixed_epoch=17,
                  epoch_source='source_validation_preselected_before_cv', test_used=False,
                  target_semantics='simulated_commercial_grade', folds=rows,
                  mean_quality_macro_f1=mean(row['quality_macro_f1'] for row in rows),
                  mean_cultivar_macro_f1=mean(row['cultivar_macro_f1'] for row in rows))
    (args.root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'cv_complete quality_macro_f1={report["mean_quality_macro_f1"]:.6f}', flush=True)


if __name__ == '__main__':
    main()
