# StarLock Python 服务端 SDK

Python 3.10+ 的同步客户端，使用标准库，通过 HTTP/JSON 创建会话与复核一次性凭证。支持当前八种题型。

## 安装

在源码仓库根目录运行以下命令。

```bash
pip install ./sdks/python
```

也可从 GitHub 源码安装。

```bash
pip install 'git+https://github.com/StarDreamTech/starlock.git@main#subdirectory=sdks/python'
```

包名为 `starlock-sdk`，导入名为 `starlock`。PyPI 尚未发布。

## 创建会话

站点须已登记应用来源、业务动作和题型。配置从业务后端私有环境读取，以下变量值由部署方提供。

```python
import os
from dataclasses import asdict
from starlock import Client, StarLockError

client = Client(
    api_base=os.environ['STARLOCK_API_BASE'],
    site_key=os.environ['STARLOCK_SITE_KEY'],
    site_secret=os.environ['STARLOCK_SITE_SECRET'],
    timeout=10,
)

# trusted_context_id 由业务后端生成，并保存在其会话中。
def create_challenge(trusted_context_id: str) -> dict:
    session = client.create_session(
        action='login', context_id=trusted_context_id,
        origin=os.environ['STARLOCK_APP_ORIGIN'],
        challenge_type='semantic_grid',
    )
    return asdict(session)
```

将返回值中的 `site_key`、`session_ticket` 交给已有 HTML、Vue 或 React 验证组件。

## 复核凭证

前端完成挑战后将 token 交给业务后端。业务后端从自己的会话读取上下文。

```python
def verify_login(token: str, trusted_context_id: str) -> bool:
    try:
        result = client.siteverify(
            token=token, action='login', context_id=trusted_context_id,
        )
    except StarLockError as error:
        # 可记录 error.code、error.request_id，并向业务返回验证失败。
        return False
    return result.success
```

`create_session` 还接受 `rotation_source` 与 `image_set_id`，仅在提供值时发送。参数规则与服务端一致，详见 [统一接入说明](../../docs/server-sdks.md)。

网络超时默认十秒，`ssl_context` 可配置受信任的私有 CA。SDK 保留 API 错误的 `code`、`message`、`status_code`、`request_id`、`retry_after`，并验证成功响应的站点、动作和上下文。API 地址支持网关路径前缀。

SDK 禁止 HTTP 重定向以限定凭据发送位置，不自动重试。网络失败时操作结果可能未知，复核凭证可能已被消费，按业务流程要求重新验证。Python 客户端为同步调用，FastAPI 普通 `def` 路由可直接使用；在 `async def` 中应通过线程池调用。

## 测试

从仓库根目录运行。

```bash
PYTHONPATH=sdks/python/src python -m unittest discover -s sdks/python/tests -v
```
