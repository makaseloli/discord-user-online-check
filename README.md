# Discord User Checker
ユーザーがオンラインかどうかを確認するDiscordボットです。
## 使い方
```sh
git clone https://github.com/makaseloli/discord-user-online-check.git
docker compose up
curl http://localhost:8765/<Snowflake>
```

## 機能
ユーザーがオンラインなら200、オフラインなら500を返します。
UptimeKumaなどの監視アプリと組み合わせて使用してください。
