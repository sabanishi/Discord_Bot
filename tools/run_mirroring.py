import asyncio
from typing import Mapping

import aiohttp

from app.config import AppConfig, load_config
from app.mirroring import MirrorCosenseClient, MirrorRunResult, MirrorService


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


def main() -> None:
    result = asyncio.run(run_once())
    print_result(result)


if __name__ == "__main__":
    main()
