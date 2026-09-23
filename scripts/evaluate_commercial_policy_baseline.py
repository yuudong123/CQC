"""Compare v2 plus the fixed rule with synthetic commercial targets on reused Test."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from src.data.virtual_brix import load_virtual_brix
from src.inference.commercial_policy import assess_commercial_grade, POLICY_VERSION
from src.training.engine import classification_metrics

CLASSES = ('L', 'M', 'S')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v2-predictions', type=Path, default=Path('docs/wbs/results/candidate-v2-reused-test-regression.json'))
    parser.add_argument('--virtual-brix', type=Path, default=Path('data/processed/virtual-brix.csv'))
    parser.add_argument('--output', type=Path, default=Path('docs/wbs/results/commercial-v2-rule-reused-test.json'))
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f'Refusing to overwrite: {args.output}')
    source = json.loads(args.v2_predictions.read_text(encoding='utf-8'))
    brix = load_virtual_brix(args.virtual_brix)
    matrix = torch.zeros((3, 3), dtype=torch.long)
    seen = set()
    for row in source['test']['predictions']:
        key = row['group_no']
        if key in seen:
            raise ValueError(f'Duplicate apple in Test: {key}')
        seen.add(key)
        value = brix[key][0]
        actual = assess_commercial_grade(CLASSES[row['quality_target_index']], value)['commercial_grade']
        predicted = assess_commercial_grade(CLASSES[row['quality_prediction_index']], value)['commercial_grade']
        matrix[CLASSES.index(actual), CLASSES.index(predicted)] += 1
    if len(seen) != 27:
        raise ValueError(f'Expected 27 apples, found {len(seen)}')
    result = dict(evaluation_role='reused_test_diagnostic_simulated_commercial_target',
                  independent_final_approval=False, may_select_model_or_epoch=False,
                  method='v2_appearance_prediction_plus_exact_demo_commercial_rule',
                  policy_version=POLICY_VERSION, brix_is_measured=False,
                  samples=len(seen), commercial=classification_metrics(matrix))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'commercial_macro_f1={result["commercial"]["macro_f1"]:.6f}')


if __name__ == '__main__':
    main()
