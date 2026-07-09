"""LLM 设置 API：用户从 UI 管理 API key、模型、base URL。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core import storage
from app.core.models import (
    LLM_MODEL_PRESETS,
    LLMBackend,
    LLMSettings,
    LLMSettingsPublic,
    LLMSettingsUpdate,
    mask_key,
)
from app.llm.router import (
    DB_CONFIG_KEY,
    get_active_settings_with_source,
    get_verified_client,
    load_settings_from_env,
    reset_client,
)

router = APIRouter()


class LLMSettingsResponse(BaseModel):
    """当前 LLM 配置（脱敏）。"""
    db_config: LLMSettingsPublic | None
    env_config: LLMSettingsPublic
    active_source: str
    available: bool
    active_backend: str | None = None
    active_model: str | None = None


class ModelPresetsResponse(BaseModel):
    """各后端的模型预设。"""
    presets: dict[str, list[str]]


@router.get("/llm", response_model=LLMSettingsResponse)
async def get_llm_settings():
    """获取 LLM 设置（DB + env）。"""
    # DB 配置
    db_raw = await storage.get_setting(DB_CONFIG_KEY)
    db_config = None
    if db_raw:
        try:
            cfg = LLMSettings.model_validate_json(db_raw)
            db_config = LLMSettingsPublic(
                backend=cfg.backend,
                model=cfg.model,
                api_key_masked=mask_key(cfg.api_key),
                base_url=cfg.base_url,
                has_key=bool(cfg.api_key),
                source="db",
            )
        except Exception:
            pass

    # Env 配置
    env_cfg = load_settings_from_env()
    env_config = LLMSettingsPublic(
        backend=env_cfg.backend,
        model=env_cfg.model,
        api_key_masked=mask_key(env_cfg.api_key),
        base_url=env_cfg.base_url,
        has_key=bool(env_cfg.api_key),
        source="env",
    )

    # 验证当前可用
    client = await get_verified_client()
    available = client is not None
    active_backend = None
    active_model = None
    if client is not None:
        active_backend = client.__class__.__name__
        active_model = client.model

    # 判断 active_source
    active_source = "env"
    if db_config is not None and available:
        # 检查 active 是不是来自 db（通过 model 匹配）
        cfg_active, src = await get_active_settings_with_source()
        active_source = src

    return LLMSettingsResponse(
        db_config=db_config,
        env_config=env_config,
        active_source=active_source,
        available=available,
        active_backend=active_backend,
        active_model=active_model,
    )


@router.post("/llm", response_model=LLMSettingsPublic)
async def save_llm_settings(data: LLMSettingsUpdate):
    """保存 LLM 配置到 DB。

    行为：
    - 没传 backend：保留现有 backend
    - 传了 backend 且与现有不同：重置 api_key（让用户重新填），
      重置 base_url（除非用户也传了）
    - api_key 传空字符串 = 清除
    - 传 None 的字段保留
    """
    # 读现有配置
    existing_raw = await storage.get_setting(DB_CONFIG_KEY)
    if existing_raw:
        existing = LLMSettings.model_validate_json(existing_raw)
    else:
        existing = load_settings_from_env()

    new_data = data.model_dump(exclude_unset=True)
    backend_changed = False

    if "backend" in new_data:
        new_backend = LLMBackend(new_data["backend"])
        if new_backend != existing.backend:
            backend_changed = True
        existing.backend = new_backend
    if "model" in new_data and new_data["model"]:
        existing.model = new_data["model"]
    if "api_key" in new_data:
        # 空字符串清除，否则取新值
        existing.api_key = new_data["api_key"] or None
    if "base_url" in new_data:
        existing.base_url = new_data["base_url"] or None

    # 切换后端时：如果用户没传新 key，清空让用户重新填
    # 如果用户传了新 key（即使 backend 也变了），保留用户的 key
    if backend_changed:
        if "api_key" not in new_data:
            existing.api_key = None
        # base_url 如果没新传，重置为默认
        if "base_url" not in new_data:
            default_urls = {
                LLMBackend.ANTHROPIC: "https://api.anthropic.com",
                LLMBackend.DEEPSEEK: "https://api.deepseek.com/v1",
                LLMBackend.MINIMAX: "https://api.minimax.chat/v1",
                LLMBackend.OPENAI: "https://api.openai.com/v1",
                LLMBackend.CUSTOM: None,
            }
            existing.base_url = default_urls.get(existing.backend)

    # 验证配置完整性（注意：切换后端时清空 key 是允许的，
    # 这样用户能保存"切了后端但还没填 key"的中间态，调用 LLM 时再报错）
    if not backend_changed:
        # 只在没切换时强制要求 key
        if existing.backend in (
            LLMBackend.ANTHROPIC,
            LLMBackend.DEEPSEEK,
            LLMBackend.MINIMAX,
            LLMBackend.OPENAI,
            LLMBackend.CUSTOM,
        ):
            if not existing.api_key:
                raise HTTPException(400, f"{existing.backend.value} 需要 api_key")
    # base_url 始终要校验
    if existing.backend in (
        LLMBackend.DEEPSEEK,
        LLMBackend.MINIMAX,
        LLMBackend.OPENAI,
        LLMBackend.CUSTOM,
    ):
        if not existing.base_url:
            raise HTTPException(400, f"{existing.backend.value} 需要 base_url")

    # 保存
    await storage.set_setting(DB_CONFIG_KEY, existing.model_dump_json())
    reset_client()  # 触发重新加载

    return LLMSettingsPublic(
        backend=existing.backend,
        model=existing.model,
        api_key_masked=mask_key(existing.api_key),
        base_url=existing.base_url,
        has_key=bool(existing.api_key),
        source="db",
    )


@router.delete("/llm")
async def clear_llm_settings():
    """清除 DB 配置（回退到 env）。"""
    deleted = await storage.delete_setting(DB_CONFIG_KEY)
    reset_client()
    return {"ok": True, "deleted": deleted}


@router.get("/llm/presets", response_model=ModelPresetsResponse)
async def get_model_presets():
    """返回各后端的模型预设（前端下拉用）。"""
    return ModelPresetsResponse(presets=LLM_MODEL_PRESETS)


@router.post("/llm/test")
async def test_llm_connection(data: LLMSettingsUpdate):
    """用指定配置测试连接（不保存到 DB）。

    用于"测试连接"按钮。
    """
    # 构造测试配置
    if data.backend:
        test_cfg = LLMSettings(
            backend=data.backend,
            model=data.model or "claude-sonnet-4-5",
            api_key=data.api_key,
            base_url=data.base_url,
        )
    else:
        test_cfg = load_settings_from_env()

    from app.llm.router import _try_create_from_settings
    client = _try_create_from_settings(test_cfg)
    if client is None:
        return {"ok": False, "error": "无法创建客户端（检查 api_key / base_url）"}

    try:
        ok = await client.health_check()
        return {"ok": ok, "backend": test_cfg.backend.value, "model": test_cfg.model}
    except Exception as e:
        return {"ok": False, "error": str(e)}
