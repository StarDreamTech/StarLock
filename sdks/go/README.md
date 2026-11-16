# StarLock Go 服务端 SDK

Go 1.22+ 客户端，使用标准库，支持八种题型的会话创建与一次性凭证复核。可在标准 HTTP 服务、Gin、Echo 等业务后端调用。

## 安装

```bash
go get github.com/StarDreamTech/starlock/sdks/go@main
```

当前通过源码分支提供模块，版本标签尚未发布。部署时可固定已验证的提交版本。

## 使用

以下函数从私有环境读取配置，接入方从业务后端的会话中传入上下文。

```go
package backend

import (
    "context"
    "os"

    starlock "github.com/StarDreamTech/starlock/sdks/go"
)

func NewVerifier() (*starlock.Client, error) {
    return starlock.NewClient(starlock.Config{
        APIBase: os.Getenv("STARLOCK_API_BASE"),
        SiteKey: os.Getenv("STARLOCK_SITE_KEY"),
        SiteSecret: os.Getenv("STARLOCK_SITE_SECRET"),
    })
}

func CreateChallenge(ctx context.Context, client *starlock.Client, trustedContextID string) (*starlock.Session, error) {
    return client.CreateSession(ctx, starlock.SessionRequest{
        Action: "login", ContextID: trustedContextID,
        Origin: os.Getenv("STARLOCK_APP_ORIGIN"),
        ChallengeType: starlock.SemanticGrid,
    })
}

func VerifyLogin(ctx context.Context, client *starlock.Client, token, trustedContextID string) (*starlock.VerificationResult, error) {
    return client.SiteVerify(ctx, starlock.VerifyRequest{
        Token: token, Action: "login", ContextID: trustedContextID,
    })
}
```

将会话里的 `SiteKey` 与 `SessionTicket` 交给已有 HTML、Vue 或 React 组件。验证后由业务后端复核 token，成功后幂等执行业务。

`SessionRequest` 支持 `RotationSource`、`ImageSetID`，省略题型时默认 `Text`。题型常量还包括 `Digits`、`Arithmetic`、`Slider`、`BezierSlider`、`Rotate`、`TextClick` 和 `SemanticGrid`。

使用 `errors.As(err, &failure)` 提取 `*starlock.Error`，读取 `Code`、`Message`、`StatusCode`、`RequestID` 与 `RetryAfter`。上下文取消和截止时间可用 `errors.Is` 判断。客户端可并发复用，默认 HTTP 超时十秒，可通过 `Config.HTTPClient` 配置传输与超时。

API 地址支持网关路径前缀。SDK 禁止 HTTP 重定向以限定凭据发送位置，不自动重试。复核期间网络失败时凭证可能已被消费，需按业务流程重新验证。更多流程见 [服务端 SDK 指南](../../docs/server-sdks.md)。

## 测试

```bash
go test -race -count=1 -timeout=30s ./...
go vet ./...
```

真实 API 集成由仓库服务端测试启动隔离服务、Redis 命名空间和站点，再运行 `TestLiveAPI`；单独运行模块测试时该项会跳过。
