import asyncio
import argparse
from typing import Mapping

import aiohttp

from app.config import AppConfig, load_config
from app.mirroring import (
    MirrorCosenseClient,
    MirrorPreviewResult,
    MirrorRunResult,
    MirrorService,
)


def _required(value: str | None, env_name: str) -> str:
    if not value or not value.strip():
        raise RuntimeError(f"環境変数 {env_name} が設定されていません")
    return value.strip()


def _build_service(config: AppConfig, session: aiohttp.ClientSession) -> MirrorService:
    source_project = _required(config.cosense_project, "COSENSE_PROJECT")
    sid = _required(config.cosense_sid, "COSENSE_SID")
    public_project = _required(
        config.mirror_public_project, "MIRROR_PUBLIC_PROJECT"
    )
    exclusion_page = _required(
        config.mirror_exclusion_config_page,
        "MIRROR_EXCLUSION_CONFIG_PAGE",
    )
    replacement_page = _required(
        config.mirror_replacement_config_page,
        "MIRROR_REPLACEMENT_CONFIG_PAGE",
    )
    return MirrorService(
        MirrorCosenseClient(source_project, sid, session=session),
        MirrorCosenseClient(public_project, sid, session=session),
        exclusion_page,
        replacement_page,
    )


def _validate_config(config: AppConfig) -> None:
    _required(config.cosense_project, "COSENSE_PROJECT")
    _required(config.cosense_sid, "COSENSE_SID")
    _required(config.mirror_public_project, "MIRROR_PUBLIC_PROJECT")
    _required(config.mirror_exclusion_config_page, "MIRROR_EXCLUSION_CONFIG_PAGE")
    _required(config.mirror_replacement_config_page, "MIRROR_REPLACEMENT_CONFIG_PAGE")


async def run_once(environ: Mapping[str, str] | None = None) -> MirrorRunResult:
    config = load_config(environ)
    _validate_config(config)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        service = _build_service(config, session)
        return await service.run()


async def preview_once(environ: Mapping[str, str] | None = None) -> MirrorPreviewResult:
    config = load_config(environ)
    _validate_config(config)
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        service = _build_service(config, session)
        return await service.preview()


def print_result(result: MirrorRunResult) -> None:
    print(
        "ミラーリングが完了しました: "
        f"取り込み={result.imported_pages}, "
        f"作成={result.created_pages}, "
        f"更新={result.updated_pages}, "
        f"削除={result.deleted_pages}, "
        f"除外={result.excluded_pages}, "
        f"失敗={result.failed_pages}",
        flush=True,
    )


def print_preview(result: MirrorPreviewResult) -> None:
    print("ミラーリングプレビュー（Publicへの書き込みなし）", flush=True)
    print("\n置換ルール:", flush=True)
    if result.replacement_rules:
        for source, replacement in result.replacement_rules.items():
            print(f"- {source} => {replacement}", flush=True)
    else:
        print("- なし", flush=True)

    print("\nミラーリング対象ページ:", flush=True)
    if result.included_titles:
        for source, destination in result.included_titles:
            if source == destination:
                print(f"- {source}", flush=True)
            else:
                print(f"- {source} => {destination}", flush=True)
    else:
        print("- なし", flush=True)

    print("\n除外ページ:", flush=True)
    if result.excluded_titles:
        for title in result.excluded_titles:
            print(f"- {title}", flush=True)
    else:
        print("- なし", flush=True)

    if result.failed_titles:
        print("\n判定・変換に失敗したページ:", flush=True)
        for title in result.failed_titles:
            print(f"- {title}", flush=True)

    if result.title_collisions:
        print("\n置換後にタイトルが重複するページ:", flush=True)
        for title in result.title_collisions:
            print(f"- {title}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrapboxのミラーリングを実行します")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Publicプロジェクトへ書き込まず、対象ページと置換ルールだけ表示する",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.preview:
        print_preview(asyncio.run(preview_once()))
    else:
        print_result(asyncio.run(run_once()))


if __name__ == "__main__":
    main()
