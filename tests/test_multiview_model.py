from __future__ import annotations

import unittest


try:
    import torch
    from src.models.multiview import MultiViewBaseline
except (ImportError, OSError):
    torch = None
    MultiViewBaseline = None


@unittest.skipIf(torch is None, "PyTorch 실행 환경이 없습니다")
class MultiViewBaselineTest(unittest.TestCase):
    def test_masked_mean_ignores_padding(self) -> None:
        features = torch.tensor([[[1.0, 3.0], [3.0, 5.0], [100.0, 100.0]]])
        mask = torch.tensor([[True, True, False]])
        result = MultiViewBaseline.masked_mean(features, mask)
        self.assertTrue(torch.equal(torch.tensor([[2.0, 4.0]]), result))

    def test_forward_returns_both_tasks(self) -> None:
        model = MultiViewBaseline(pretrained=False).eval()
        images = torch.zeros(2, 4, 3, 64, 64)
        mask = torch.tensor([[True] * 4, [True, True, False, False]])
        with torch.no_grad():
            result = model(images, mask)
        self.assertEqual((2, 2), tuple(result["cultivar_logits"].shape))
        self.assertEqual((2, 3), tuple(result["quality_logits"].shape))


if __name__ == "__main__":
    unittest.main()
