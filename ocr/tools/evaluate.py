from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.imaging import validate_image_bytes  # noqa: E402
from app.local_ocr import LocalPaddleOCR  # noqa: E402
from app.metrics import (  # noqa: E402
    boundary_miss_rate,
    character_error_rate,
    introduced_duplicate_rate,
    key_field_accuracy,
    line_recall,
    summarize,
)
from app.pipeline import OCRPipeline  # noqa: E402
from app.policy import FreePolicy, PolicyViolation  # noqa: E402
from app.schemas import OCRJobRequest, SessionInfo, utc_now  # noqa: E402
from app.siliconflow import SiliconFlowOCRClient  # noqa: E402
from app.storage import (  # noqa: E402
    ChunkCache,
    JobStore,
    SessionStore,
    UsageLedger,
)


def load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("manifest 必须是 JSON 数组或包含 items 数组的对象。")
    return items


def load_image_bytes(item: dict[str, Any], manifest_path: Path, image_root: Path | None) -> bytes:
    image_path = Path(item["image"])
    if not image_path.is_absolute():
        image_path = (
            (image_root / image_path) if image_root else (manifest_path.parent / image_path)
        )
    return image_path.read_bytes()


async def evaluate_item(
    *,
    item: dict[str, Any],
    manifest_path: Path,
    image_root: Path | None,
    settings,
    pipeline: OCRPipeline,
    sessions: SessionStore,
    jobs: JobStore,
    variant: str,
    keep: bool,
) -> dict[str, Any]:
    item_id = str(item.get("id") or item.get("image") or "unknown")
    started = time.monotonic()
    session_id: str | None = None
    job_id: str | None = None
    try:
        raw = load_image_bytes(item, manifest_path, image_root)
        loaded = validate_image_bytes(raw, settings)
        session_id, session_dir = sessions.create()
        info = sessions.add_image(
            session_dir,
            0,
            item.get("image", "image"),
            loaded.image,
            loaded.sha256,
            loaded.source_format,
        )
        session = SessionInfo(session_id=session_id, created_at=utc_now(), images=[info])
        sessions.save_session(session_dir, session)
        payload = OCRJobRequest(
            session_id=session_id,
            consent_cloud_upload=True,
            image_order=[info.image_id],
            mode=item.get("mode", settings.prompt_mode),
            variant=variant,
            use_review=True,
            use_cache=True,
        )
        job_id = jobs.create(payload.model_dump())
        await pipeline.run_job(job_id)
        result = jobs.load_result(job_id)
        text = result.text
        reference = item.get("ground_truth_text", "")
        fields = result.images[0].key_fields if result.images else []
        expected_fields = item.get("key_fields", {}) or {}
        field_accuracy, field_details = key_field_accuracy(expected_fields, fields)
        boundary = boundary_miss_rate(item.get("boundary_texts", []) or [], text)
        latency_ms = int((time.monotonic() - started) * 1000)
        return {
            "id": item_id,
            "category": item.get("category", "uncategorized"),
            "status": result.status,
            "notes": item.get("notes", ""),
            "metrics": {
                "cer": character_error_rate(reference, text) if reference else None,
                "line_recall": line_recall(reference, text) if reference else None,
                "key_field_accuracy": field_accuracy if expected_fields else None,
                "key_field_total": field_details["total"],
                "key_field_details": field_details["details"],
                "introduced_duplicate_rate": introduced_duplicate_rate(reference, text)
                if reference
                else None,
                "boundary_miss_rate": boundary,
            },
            "needs_manual_check": result.needs_manual_check,
            "api_requests": result.api_requests,
            "cache_hits": int((result.budget or {}).get("cache_hits", 0)),
            "latency_ms": latency_ms,
            "errors": result.errors,
            "warnings": result.warnings,
            "text_preview": text[:400],
        }
    except (PolicyViolation, FileNotFoundError, ValueError) as exc:
        return {
            "id": item_id,
            "category": item.get("category", "uncategorized"),
            "status": "blocked_or_invalid",
            "error": f"{type(exc).__name__}: {exc}",
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    finally:
        if not keep:
            if job_id:
                shutil.rmtree(settings.jobs_dir / job_id, ignore_errors=True)
            if session_id:
                shutil.rmtree(settings.sessions_dir / session_id, ignore_errors=True)


def aggregate(items: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [item for item in items if item.get("metrics")]
    metrics = [item["metrics"] for item in successful]
    aggregate_payload = {
        "items": len(items),
        "evaluated": len(successful),
        "status_counts": {},
        "cer": summarize([item.get("cer") for item in metrics]),
        "line_recall": summarize([item.get("line_recall") for item in metrics]),
        "key_field_accuracy": summarize(
            [
                item.get("key_field_accuracy")
                for item in metrics
                if item.get("key_field_total", 0) > 0
            ]
        ),
        "introduced_duplicate_rate": summarize(
            [item.get("introduced_duplicate_rate") for item in metrics]
        ),
        "boundary_miss_rate": summarize([item.get("boundary_miss_rate") for item in metrics]),
        "latency_ms": summarize([item.get("latency_ms") for item in successful]),
        "api_requests": summarize([item.get("api_requests") for item in successful]),
        "cache_hits": summarize([item.get("cache_hits") for item in successful]),
        "needs_manual_check_rate": (
            sum(1 for item in successful if item.get("needs_manual_check")) / len(successful)
            if successful
            else None
        ),
    }
    for item in items:
        status = str(item.get("status"))
        aggregate_payload["status_counts"][status] = (
            aggregate_payload["status_counts"].get(status, 0) + 1
        )
    return aggregate_payload


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 电商详情页 OCR 评测报告",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 数据集：`{report['dataset']}`",
        f"- 标注样本数：{report['sample_count']}",
        f"- 说明：{report['notes']}",
        "",
        "## 汇总",
        "",
        "| 方案 | 评估数 | CER 均值 | 行召回均值 | 关键字段完全正确率 | 重复引入率 | P95 延迟(ms) | 单图请求均值 | 缓存命中均值 | 需人工核验率 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for variant, variant_payload in report["variants"].items():
        aggregate_payload = variant_payload.get("aggregate", variant_payload)

        def value(payload: dict[str, Any], name: str, key: str = "mean") -> str:
            metric = payload.get(name)
            result = metric.get(key) if isinstance(metric, dict) else metric
            if result is None:
                return "—"
            if name in {"latency_ms", "api_requests", "cache_hits"}:
                return f"{result:.1f}"
            return f"{result * 100:.2f}%"

        lines.append(
            f"| {variant} | {aggregate_payload['evaluated']} | {value(aggregate_payload, 'cer')} | "
            f"{value(aggregate_payload, 'line_recall')} | "
            f"{value(aggregate_payload, 'key_field_accuracy')} | "
            f"{value(aggregate_payload, 'introduced_duplicate_rate')} | "
            f"{value(aggregate_payload, 'latency_ms', 'p95')} | "
            f"{value(aggregate_payload, 'api_requests')} | "
            f"{value(aggregate_payload, 'cache_hits')} | "
            f"{value(aggregate_payload, 'needs_manual_check_rate')} |"
        )
    lines += [
        "",
        "## 指标口径",
        "",
        "- CER：参考文本与识别文本按 NFKC 归一化并去除空白后计算字符编辑距离 / 参考字符数。",
        "- 行召回：参考文本中能在识别结果中完整找到的非空行占比（无标注框，仅作近似）。",
        "- 关键字段：标注字段与结构化提取值归一化后完全相等。",
        "- 重复引入率：输出重复行比例减去参考文本重复行比例，低于 0 时按 0 计。",
        "- 边界漏字率：仅在清单提供 boundary_texts 时计算，否则显示为 —。",
        "- 延迟包含上传解码、分块、API 往返与合并；P95 为样本内百分位。",
        "- 单图请求次数与缓存命中分别记录；使用 `--no-cache` 时请求次数为真实独立运行值。",
        "",
        "> 上述结果只对当前标注样本有效，不代表所有电商详情页的普遍精度。",
        "",
    ]
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="在带人工标注的电商详情页测试集上评估 A/B/C/D 四种方案。"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--variants", default="B,C,D")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--image-root", type=Path)
    parser.add_argument("--output", type=Path, default=Path(".data") / "evaluation" / "report.json")
    parser.add_argument("--keep", action="store_true", help="保留会话与任务中间文件")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="禁用分块缓存，确保报告中请求次数与延迟是真实独立运行的数值",
    )
    parser.add_argument("--real", action="store_true", help="确认调用免费云端模型")
    args = parser.parse_args()
    if not args.real:
        print("评测会调用云端免费模型，必须显式传入 --real。")
        return 2
    settings = get_settings()
    if args.no_cache:
        settings.cache_enabled = False
    if not settings.api_key_configured:
        print("缺少 SILICONFLOW_API_KEY。")
        return 2
    items = load_manifest(args.manifest)
    if not items:
        print("测试集为空。必须先导入真实图片并完成人工标注，禁止编造精度结果。")
        return 2
    if args.limit:
        items = items[: args.limit]
    variants = [part.strip().upper() for part in args.variants.split(",") if part.strip()]
    invalid = [variant for variant in variants if variant not in {"A", "B", "C", "D"}]
    if invalid:
        print(f"未知方案：{invalid}")
        return 2

    policy = FreePolicy(settings)
    status = await policy.refresh(force=True)
    print("免费策略：", json.dumps(status["models"], ensure_ascii=False))
    policy.assert_free(settings.primary_model)
    if any(variant in {"C", "D"} for variant in variants):
        try:
            policy.assert_free(settings.review_model)
        except PolicyViolation as exc:
            print(f"复核模型不可用，将跳过复核：{exc}")

    cache = ChunkCache(settings)
    client = SiliconFlowOCRClient(settings, policy, cache)
    sessions = SessionStore(settings)
    jobs = JobStore(settings)
    ledger = UsageLedger(settings)
    local_ocr = LocalPaddleOCR(settings)
    pipeline = OCRPipeline(settings, policy, client, sessions, jobs, ledger, local_ocr)

    report: dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "dataset": str(args.manifest),
        "sample_count": len(items),
        "notes": "仅基于当前人工标注样本；空测试集或未标注项不会产生精度结论。",
        "policy": policy.status(),
        "variants": {},
    }
    for variant in variants:
        print(f"开始方案 {variant}，样本 {len(items)} 条")
        items_report = []
        for index, item in enumerate(items, start=1):
            result = await evaluate_item(
                item=item,
                manifest_path=args.manifest,
                image_root=args.image_root,
                settings=settings,
                pipeline=pipeline,
                sessions=sessions,
                jobs=jobs,
                variant=variant,
                keep=args.keep,
            )
            items_report.append(result)
            print(
                f"  [{index}/{len(items)}] {result['id']}: {result['status']} "
                f"CER={result.get('metrics', {}).get('cer')} requests={result.get('api_requests')}"
            )
        report["variants"][variant] = {
            "aggregate": aggregate(items_report),
            "items": items_report,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"报告已写入：{args.output} 与 {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
