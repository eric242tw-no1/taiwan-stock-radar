## ADDED Requirements

### Requirement: Nginx 反向代理與 SSL 終止
系統 SHALL 透過 Nginx 作為唯一對外入口，處理 SSL 終止、靜態資源快取，並將流量分發至 Next.js 與 FastAPI。

#### Scenario: HTTPS 強制跳轉
- **WHEN** 使用者以 HTTP（port 80）存取任何路徑
- **THEN** Nginx 回傳 301 永久跳轉至 HTTPS

#### Scenario: API 流量代理至 FastAPI
- **WHEN** 請求路徑以 `/api/` 開頭
- **THEN** Nginx 將請求代理至 `fastapi:8000`，保留原始 headers

#### Scenario: 前端流量代理至 Next.js
- **WHEN** 請求路徑不以 `/api/` 開頭
- **THEN** Nginx 將請求代理至 `nextjs:3000`

#### Scenario: Next.js 靜態資源長期快取
- **WHEN** 請求路徑為 `/_next/static/`
- **THEN** Nginx 直接 serve 靜態檔案並設定 `Cache-Control: public, max-age=31536000, immutable`

### Requirement: Let's Encrypt SSL 憑證自動更新
系統 SHALL 使用 Certbot 取得並自動更新 Let's Encrypt SSL 憑證。

#### Scenario: 憑證到期前自動更新
- **WHEN** 憑證剩餘有效期少於 30 天
- **THEN** Certbot renew cron 自動更新憑證並 reload Nginx
