"""端侧（智能 IPC）：person 检测 + 跟踪去重。

见 docs/SYSTEM.md §2.1 —— 同一镜头内只对「入帧 / 姿态变化(定时采样) / 出帧」
三个时刻切图上报，把 30fps 视频压到约 1.5 张/秒/目标，去重率 95%+。

`Deduper` 是纯逻辑（不依赖检测模型），`PersonTracker` 才需要 yolo26n。

.. note::
   当前项目仅仅作为前期可行性验证使用，部分代码沿用但并不代表最终系统。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np

DEFAULT_WEIGHTS = Path(__file__).resolve().parent.parent / "models" / "yolo26n.pt"
PERSON_CLASS = 0  # COCO: person


@dataclass
class Emit:
    """一次「值得上报」的抓拍。"""

    frame: int
    track_id: int
    box: tuple  # (x1, y1, x2, y2)
    reason: str  # enter | interval | exit
    crop: np.ndarray | None = None


@dataclass
class _Track:
    last_emit: int
    box: tuple
    crop: np.ndarray | None
    miss: int = 0


class Deduper:
    """跟踪结果 -> 去重后的上报事件。纯逻辑，可单测。"""

    def __init__(self, interval=30, miss_tolerance=3):
        self.interval = interval
        self.miss_tolerance = miss_tolerance
        self._tracks: dict[int, _Track] = {}

    def update(self, frame_idx: int, tracks) -> list[Emit]:
        """tracks: [(track_id, box, crop), ...] 本帧的跟踪结果。"""
        emits: list[Emit] = []
        alive = set()
        for tid, box, crop in tracks:
            alive.add(tid)
            rec = self._tracks.get(tid)
            if rec is None:
                emits.append(Emit(frame_idx, tid, box, "enter", crop))
            elif frame_idx - rec.last_emit >= self.interval:
                emits.append(Emit(frame_idx, tid, box, "interval", crop))
            else:
                # 未达上报节流：只刷新缓存，供出帧时使用
                self._tracks[tid] = replace(rec, box=box, crop=crop, miss=0)
                continue
            self._tracks[tid] = _Track(frame_idx, box, crop)

        for tid, rec in list(self._tracks.items()):
            if tid in alive:
                continue
            if rec.miss + 1 >= self.miss_tolerance:  # 容忍几帧漏检，避免误判出帧
                emits.append(Emit(frame_idx, tid, rec.box, "exit", rec.crop))
                del self._tracks[tid]
            else:
                self._tracks[tid] = replace(rec, miss=rec.miss + 1)
        return emits


def crop_box(frame: np.ndarray, box) -> np.ndarray:
    x1, y1, x2, y2 = (int(v) for v in box)
    h, w = frame.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    return frame[y1:y2, x1:x2].copy()


_detector = None


def get_detector(weights=DEFAULT_WEIGHTS, device=None):
    """进程内复用一个 YOLO 实例，避免每次请求都重新加载权重。"""
    global _detector
    if _detector is None:
        from ultralytics import YOLO

        _detector = YOLO(weights)
        if device:
            _detector.to(device)
    return _detector


class PersonTracker:
    """yolo26n person 检测 + ByteTrack 跟踪 + Deduper 去重。"""

    def __init__(self, weights=DEFAULT_WEIGHTS, device=None, interval=30, conf=0.35):
        self.model = get_detector(weights, device)
        self.conf = conf
        self.interval = interval
        self.deduper = Deduper(interval=interval)
        self.reset_stats()

    def reset(self):
        """清空跟踪状态，让同一模型实例可以被下一段视频复用。"""
        self.deduper = Deduper(interval=self.interval)
        self.reset_stats()
        for tracker in getattr(getattr(self.model, "predictor", None), "trackers", None) or []:
            tracker.reset()

    def reset_stats(self):
        self.frames = self.detections = self.emits = 0
        self.by_reason = {"enter": 0, "interval": 0, "exit": 0}

    def stream(self, frames):
        """frames: 可迭代的 BGR ndarray -> 逐条 yield 去重后的 Emit。"""
        for i, frame in enumerate(frames):
            self.frames += 1
            result = self.model.track(
                frame, persist=True, classes=[PERSON_CLASS], conf=self.conf,
                tracker="bytetrack.yaml", verbose=False,
            )[0]
            tracks = []
            if result.boxes is not None and result.boxes.id is not None:
                ids = result.boxes.id.int().cpu().tolist()
                boxes = result.boxes.xyxy.cpu().numpy().astype(int)
                for tid, box in zip(ids, boxes):
                    tracks.append((tid, tuple(box.tolist()), crop_box(frame, box)))
            self.detections += len(tracks)
            for emit in self.deduper.update(i, tracks):
                self.emits += 1
                self.by_reason[emit.reason] += 1
                yield emit

    def stats(self) -> dict:
        return {
            "frames": self.frames,
            "detections": self.detections,
            "emits": self.emits,
            "by_reason": dict(self.by_reason),
            "dedup_rate": round(1 - self.emits / self.detections, 4) if self.detections else 0.0,
        }


def detect_persons(image, conf=0.35, weights=DEFAULT_WEIGHTS, device=None):
    """单图检测（不做跟踪），返回 [{box, score, crop}]。"""
    model = get_detector(weights, device)
    result = model.predict(image, classes=[PERSON_CLASS], conf=conf, verbose=False)[0]
    out = []
    if result.boxes is not None:
        for box, score in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy()):
            box = tuple(int(v) for v in box)
            out.append({"box": box, "score": float(score), "crop": crop_box(image, box)})
    return out


def make_demo_sequence(crops, frames=90, size=(1280, 720)):
    """把若干人物裁图贴在画布上缓慢移动，合成一段"摄像头视频"，用于演示跟踪去重。

    数据集的 gallery/probe 都是单张裁图，没有真实视频，所以用这种方式造一段
    多目标、有位移、有进出画面的序列来跑真正的 yolo26n + ByteTrack。
    """
    h, w = size
    canvas = np.full((frames, h, w, 3), 60, dtype=np.uint8)
    rng = np.random.default_rng(0)
    for idx, crop in enumerate(crops):
        scale = 300 / max(crop.shape[0], 1)
        person = cv2.resize(crop, (int(crop.shape[1] * scale), 300))
        ph, pw = person.shape[:2]
        x = int(rng.uniform(0, max(1, w - pw)))
        y = int(rng.uniform(80, max(81, h - ph)))
        vx = float(rng.uniform(-4, 4))
        vy = float(rng.uniform(-1.5, 1.5))
        for f in range(frames):
            px, py = int(x + vx * f) % max(1, w - pw), int(np.clip(y + vy * f, 0, h - ph))
            canvas[f, py : py + ph, px : px + pw] = person
    return list(canvas)


def _demo():
    """自检：不依赖模型，验证去重节流与出帧上报逻辑。"""
    d = Deduper(interval=10, miss_tolerance=2)
    box, crop = (0, 0, 10, 20), np.zeros((20, 10, 3), np.uint8)
    reasons = []
    for f in range(25):  # 单目标连续 25 帧
        reasons += [e.reason for e in d.update(f, [(7, box, crop)])]
    assert reasons == ["enter", "interval", "interval"], reasons  # 25 帧只上报 3 次

    reasons = [e.reason for e in d.update(25, [])]  # 第 1 帧漏检，容忍
    assert reasons == [], reasons
    reasons = [e.reason for e in d.update(26, [])]  # 第 2 帧仍缺失 -> 出帧
    assert reasons == ["exit"], reasons

    d2 = Deduper(interval=10)
    assert [e.reason for e in d2.update(0, [(1, box, crop), (2, box, crop)])] == ["enter", "enter"]
    assert [e.reason for e in d2.update(1, [(1, box, crop)])] == []
    print("Deduper self-check OK")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="端侧检测+跟踪去重")
    parser.add_argument("--source", help="视频文件或图片目录；不填则只跑自检")
    parser.add_argument("--interval", type=int, default=30, help="同一目标每隔多少帧重新上报一次")
    args = parser.parse_args()

    if not args.source:
        _demo()
    else:
        cap = cv2.VideoCapture(args.source)
        assert cap.isOpened(), f"打不开 {args.source}"
        tracker = PersonTracker(interval=args.interval)

        def frames():
            while True:
                ok, frame = cap.read()
                if not ok:
                    return
                yield frame

        for emit in tracker.stream(frames()):
            print(f"[frame {emit.frame:5d}] track={emit.track_id} {emit.reason:8s} box={emit.box}")
        print(tracker.stats())
