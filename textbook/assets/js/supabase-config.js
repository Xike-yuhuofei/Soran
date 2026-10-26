/* ============================================================
   Soran 教材 · Supabase 配置
   1. 在 https://supabase.com 创建项目
   2. Settings → API Keys：
      - 新版界面复制 Publishable key（sb_publishable_ 开头）
      - 旧版界面复制 anon public key（eyJ 开头的 JWT）
   3. Project URL 在 Settings → Data API 中复制
   4. 填入下方两项并保存
   Publishable / anon key 可以公开在静态站点中，数据权限由数据库 RLS 控制；
   绝对不要把 secret key 或 service_role key 写到这里。
   ============================================================ */
window.SORAN_SUPABASE = {
  url: 'https://cgoqgerxisuntxcgkisy.supabase.co',
  anonKey: 'sb_publishable_lK5KvmDt-UmmdF0HT8xJ5Q_vHf8Ca0h'
};
