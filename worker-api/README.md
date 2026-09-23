# Thesis API

獨立的 Cloudflare Worker API，使用 `thesis-db` D1 儲存評論資料。

第一次部署前，在專案根目錄執行並自行輸入密碼，不要把密碼寫入檔案：

```bash
npx wrangler secret put ADMIN_PASSWORD --config worker-api/wrangler.jsonc
npx wrangler secret put JWT_SECRET --config worker-api/wrangler.jsonc
npx wrangler deploy --config worker-api/wrangler.jsonc
```

API 部署網址：`https://thesis-api.jinfeng8605.workers.dev`
